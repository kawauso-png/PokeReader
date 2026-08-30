#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include "title_info.h"
#include "hid.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL
#define WRAM_SLOT 0x0021B6CCu
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u

// Two lightweight LR35902-PC candidates recovered on real hardware in the
// earlier Stage 9/10 probes. v7 records both; it never scans memory while the
// critical Mewtwo transition is running.
#define PC_A_ADDR 0x0021B8F8u
#define PC_S_ADDR 0x0021B890u

#define OFF_SOUND_CH5      0x002Au  // C02A = wChannelSoundIDs + CHAN5
#define OFF_SOUND_CH6      0x002Bu
#define OFF_SOUND_CH7      0x002Cu
#define OFF_SOUND_CH8      0x002Du
#define OFF_ENEMY_SPECIES  0x0FCCu
#define OFF_ENEMY_DV0      0x0FD8u
#define OFF_ENEMY_DV1      0x0FD9u
#define OFF_ENEMY_LEVEL    0x0FDAu
#define OFF_BATTLE_STATE   0x1034u
#define OFF_OPPONENT       0x1036u
#define OFF_LOW_HEALTH     0x1083u  // D083 = wLowHealthAlarm in Japanese R/B

// HRAM base is FF80.
#define HRAM_JOY_PRESSED_OFF 0x33u  // FFB3
#define HRAM_JOY_HELD_OFF    0x34u  // FFB4
#define HRAM_ADD_OFF         0x53u  // FFD3
#define HRAM_SUB_OFF         0x54u  // FFD4
#define HRAM_FRAME_OFF       0x55u  // FFD5

#define TRACE_LEN 512u
#define TRACE_MASK (TRACE_LEN - 1u)

#define ARM_SOURCE_UNKNOWN    0u
#define ARM_SOURCE_GAME_A     1u
#define ARM_SOURCE_EXACT2F    2u
#define ARM_SOURCE_PHYSICAL_A 3u

typedef struct
{
    u32 seq;
    u32 wram;
    u32 hram;
    u32 div_ptr;
    u32 phys_keys;
    u16 rng;
    u16 raw_dv;
    u16 pc_a;
    u16 pc_s;
    u8 div;
    u8 frame;
    u8 joy_pressed;
    u8 joy_held;
    u8 species;
    u8 opponent;
    u8 battle;
    u8 level;
    u8 low_health;
    u8 snd5;
    u8 snd6;
    u8 snd7;
    u8 snd8;
} DvTraceEntry;

static DvTraceEntry trace_buf[TRACE_LEN] = {{0}};
static u32 trace_seq = 0;
static u32 live_rng = 0;
static u32 live_div = 0;
static u32 live_raw_dv = 0;
static u32 live_status = 0;
static u32 live_wram = 0;
static u32 live_hram = 0;
static u32 live_div_ptr = 0;
static u32 live_joy_pressed = 0;
static u32 live_joy_held = 0;

static bool armed = false;
static u32 pending_arm_source = ARM_SOURCE_UNKNOWN;
static u32 active_arm_source = ARM_SOURCE_UNKNOWN;
static u32 trigger_seq = 0;
static DvTraceEntry trigger_entry = {0};
static u16 baseline_dv = 0;

static u32 physical_a_seq = 0;
static u32 game_a_seq = 0;
static u32 opponent_seq = 0;
static u32 audio_start_seq = 0;
static u32 audio_end_seq = 0;
static bool lowhealth_bit7_seen = false;

static u32 dvwrite_seq = 0;
static DvTraceEntry dvwrite_entry = {0};
static DvTraceEntry pre_entry = {0};
static u32 battle_seq = 0;
static DvTraceEntry battle_entry = {0};
static u32 save_slot = 0;
static u32 save_error = 0;

static u8 d2_c0 = 0;
static u8 d2_c1 = 0;
static bool add2_matches = false;

static bool query_span_mapped(u32 start, u32 end)
{
    MemInfo info;
    PageInfo page;
    if (end < start)
        return false;
    if (svcQueryMemory(&info, &page, start) != 0)
        return false;
    if (info.state == MEMSTATE_FREE || info.state == MEMSTATE_RESERVED)
        return false;
    if (start < info.base_addr)
        return false;
    if ((start - info.base_addr) >= info.size)
        return false;
    return (end - info.base_addr) < info.size;
}

static DvTraceEntry entry_at(u32 seq)
{
    DvTraceEntry e = trace_buf[seq & TRACE_MASK];
    if (e.seq != seq)
    {
        DvTraceEntry empty = {0};
        return empty;
    }
    return e;
}

static bool shiny_from_raw(u16 raw)
{
    u8 atk = (u8)((raw >> 12) & 0x0Fu);
    u8 def = (u8)((raw >> 8) & 0x0Fu);
    u8 spe = (u8)((raw >> 4) & 0x0Fu);
    u8 spc = (u8)(raw & 0x0Fu);
    bool atk_ok = atk == 2u || atk == 3u || atk == 6u || atk == 7u ||
                  atk == 10u || atk == 11u || atk == 14u || atk == 15u;
    return atk_ok && def == 10u && spe == 10u && spc == 10u;
}

static bool wait_audio_active(DvTraceEntry e)
{
    // WaitForSoundToFinish checks CHAN5, CHAN6 and CHAN8 (not CHAN7).
    return (u8)(e.snd5 | e.snd6 | e.snd8) != 0;
}

static s32 rel_or_neg1(u32 seq)
{
    if (seq == 0 || trigger_seq == 0)
        return -1;
    return (s32)seq - (s32)trigger_seq;
}

static u32 delta_or_zero(u32 from, u32 to)
{
    if (from == 0 || to < from)
        return 0;
    return to - from;
}

static void write_bytes(Handle file, u64 *offset, const char *s, u32 len)
{
    u32 written = 0;
    if (R_SUCCEEDED(FSFILE_Write(file, &written, *offset, s, len, 0)))
        *offset += written;
}

static void write_meta_row(Handle file, u64 *off)
{
    char line[1600];
    u32 trigger_to_battle = delta_or_zero(trigger_seq, battle_seq);
    u32 physical_to_battle = delta_or_zero(physical_a_seq, battle_seq);
    u32 game_to_battle = delta_or_zero(game_a_seq, battle_seq);
    int n = snprintf(
        line, sizeof(line),
        "meta,version,title_id,arm_source,trigger_seq,physical_a_seq,game_a_seq,battle_seq,trigger_to_battle,physical_to_battle,game_to_battle,"
        "opponent_seq,opponent_rel,audio_start_seq,audio_start_rel,audio_end_seq,audio_end_rel,dvwrite_seq,dvwrite_rel,raw_dv,shiny,"
        "lowhealth_trigger,lowhealth_bit7_seen,wram,hram,div_ptr,pc_a_addr,pc_s_addr,"
        "trigger_rng_add,trigger_rng_sub,trigger_frame,trigger_div,trigger_lowhealth,trigger_snd5,trigger_snd6,trigger_snd7,trigger_snd8,"
        "pre_rng_add,pre_rng_sub,pre_frame,pre_div,dvwrite_rng_add,dvwrite_rng_sub,dvwrite_frame,dvwrite_div,"
        "battle_rng_add,battle_rng_sub,battle_frame,battle_div,d2_c0,d2_c1,add2_match\n"
        "MEWTWO,7,%016llX,%lu,%lu,%lu,%lu,%lu,%lu,%lu,%lu,"
        "%lu,%ld,%lu,%ld,%lu,%ld,%lu,%ld,%04X,%u,"
        "%02X,%u,%08lX,%08lX,%08lX,%08X,%08X,"
        "%02X,%02X,%02X,%02X,%02X,%02X,%02X,%02X,%02X,"
        "%02X,%02X,%02X,%02X,%02X,%02X,%02X,%02X,"
        "%02X,%02X,%02X,%02X,%02X,%02X,%u\n",
        (unsigned long long)BLUE_JP_TITLE_ID,
        (unsigned long)active_arm_source,
        (unsigned long)trigger_seq,
        (unsigned long)physical_a_seq,
        (unsigned long)game_a_seq,
        (unsigned long)battle_seq,
        (unsigned long)trigger_to_battle,
        (unsigned long)physical_to_battle,
        (unsigned long)game_to_battle,
        (unsigned long)opponent_seq, (long)rel_or_neg1(opponent_seq),
        (unsigned long)audio_start_seq, (long)rel_or_neg1(audio_start_seq),
        (unsigned long)audio_end_seq, (long)rel_or_neg1(audio_end_seq),
        (unsigned long)dvwrite_seq, (long)rel_or_neg1(dvwrite_seq),
        (unsigned int)battle_entry.raw_dv,
        shiny_from_raw(battle_entry.raw_dv) ? 1u : 0u,
        trigger_entry.low_health,
        lowhealth_bit7_seen ? 1u : 0u,
        (unsigned long)battle_entry.wram,
        (unsigned long)battle_entry.hram,
        (unsigned long)battle_entry.div_ptr,
        PC_A_ADDR, PC_S_ADDR,
        (u8)(trigger_entry.rng >> 8), (u8)trigger_entry.rng,
        trigger_entry.frame, trigger_entry.div, trigger_entry.low_health,
        trigger_entry.snd5, trigger_entry.snd6, trigger_entry.snd7, trigger_entry.snd8,
        (u8)(pre_entry.rng >> 8), (u8)pre_entry.rng, pre_entry.frame, pre_entry.div,
        (u8)(dvwrite_entry.rng >> 8), (u8)dvwrite_entry.rng, dvwrite_entry.frame, dvwrite_entry.div,
        (u8)(battle_entry.rng >> 8), (u8)battle_entry.rng, battle_entry.frame, battle_entry.div,
        d2_c0, d2_c1, add2_matches ? 1u : 0u);
    if (n > 0)
        write_bytes(file, off, line, (u32)n);
}

static void save_csv(void)
{
    save_error = 0;
    save_slot = 0;

    if (trigger_seq == 0 || battle_seq < trigger_seq)
        return;

    Result r = fsInit();
    if (R_FAILED(r))
    {
        save_error = (u32)r;
        return;
    }

    FS_Archive sdmc;
    r = FSUSER_OpenArchive(&sdmc, ARCHIVE_SDMC, fsMakePath(PATH_EMPTY, ""));
    if (R_FAILED(r))
    {
        save_error = (u32)r;
        fsExit();
        return;
    }

    FSUSER_CreateDirectory(sdmc, fsMakePath(PATH_ASCII, "/luma/plugins/pokereader"), 0);
    FSUSER_CreateDirectory(sdmc, fsMakePath(PATH_ASCII, "/luma/plugins/pokereader/traces"), 0);

    Handle file = 0;
    char path[128];
    u32 slot = 1;
    for (; slot <= 999u; slot++)
    {
        u64 size = 0;
        snprintf(path, sizeof(path), "/luma/plugins/pokereader/traces/mewtwo_trace_%04lu.csv", (unsigned long)slot);
        r = FSUSER_OpenFile(&file, sdmc, fsMakePath(PATH_ASCII, path), FS_OPEN_WRITE | FS_OPEN_CREATE, 0);
        if (R_FAILED(r))
            break;
        if (R_SUCCEEDED(FSFILE_GetSize(file, &size)) && size == 0)
            break;
        FSFILE_Close(file);
        file = 0;
    }

    FSUSER_CloseArchive(sdmc);
    if (R_FAILED(r) || file == 0)
    {
        save_error = (u32)r;
        fsExit();
        return;
    }

    FSFILE_SetSize(file, 0);
    u64 off = 0;
    write_meta_row(file, &off);

    const char *hdr =
        "seq,rel,rng_add,rng_sub,frame,div,raw_dv,joy_pressed,joy_held,phys_keys,phys_a,low_health,snd5,snd6,snd7,snd8,"
        "pc_a,pc_s,species,opponent,battle,level,wram,hram,div_ptr,"
        "is_trigger,is_physical_a,is_game_a,is_opponent,is_audio_start,is_audio_end,is_pre,is_dvwrite,is_battle\n";
    write_bytes(file, &off, hdr, (u32)strlen(hdr));

    u32 first = trigger_seq > 8u ? trigger_seq - 8u : 1u;
    u32 last = battle_seq;
    if (last - first >= TRACE_LEN)
        first = last - TRACE_LEN + 1u;

    char row[512];
    for (u32 seq = first; seq <= last; seq++)
    {
        DvTraceEntry e = entry_at(seq);
        if (e.seq == 0)
            continue;
        s32 rel = (s32)e.seq - (s32)trigger_seq;
        int n = snprintf(
            row, sizeof(row),
            "%lu,%ld,%02X,%02X,%02X,%02X,%04X,%02X,%02X,%08lX,%u,%02X,%02X,%02X,%02X,%02X,%04X,%04X,"
            "%02X,%02X,%02X,%02X,%08lX,%08lX,%08lX,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            (unsigned long)e.seq, (long)rel,
            (u8)(e.rng >> 8), (u8)e.rng, e.frame, e.div, e.raw_dv,
            e.joy_pressed, e.joy_held, (unsigned long)e.phys_keys,
            (e.phys_keys & KEY_A) ? 1u : 0u,
            e.low_health, e.snd5, e.snd6, e.snd7, e.snd8,
            e.pc_a, e.pc_s, e.species, e.opponent, e.battle, e.level,
            (unsigned long)e.wram, (unsigned long)e.hram, (unsigned long)e.div_ptr,
            e.seq == trigger_seq,
            e.seq == physical_a_seq,
            e.seq == game_a_seq,
            e.seq == opponent_seq,
            e.seq == audio_start_seq,
            e.seq == audio_end_seq,
            e.seq == pre_entry.seq,
            e.seq == dvwrite_seq,
            e.seq == battle_seq);
        if (n > 0)
            write_bytes(file, &off, row, (u32)n);
    }

    FSFILE_Flush(file);
    FSFILE_Close(file);
    fsExit();
    save_slot = slot;
}

u32 host_blue_dvtrace_sample(void)
{
    live_status = 0;
    live_rng = live_div = live_raw_dv = 0;
    live_wram = live_hram = live_div_ptr = 0;
    live_joy_pressed = live_joy_held = 0;

    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;
    if (!query_span_mapped(WRAM_SLOT, WRAM_SLOT + 3u) ||
        !query_span_mapped(HRAM_SLOT, HRAM_SLOT + 3u) ||
        !query_span_mapped(DIV_SLOT, DIV_SLOT + 3u))
        return 0;

    u32 wram = *(vu32 *)WRAM_SLOT;
    u32 hram = *(vu32 *)HRAM_SLOT;
    u32 divp = *(vu32 *)DIV_SLOT;
    if (!query_span_mapped(wram + OFF_SOUND_CH5, wram + OFF_LOW_HEALTH) ||
        !query_span_mapped(hram + HRAM_JOY_PRESSED_OFF, hram + HRAM_FRAME_OFF) ||
        !query_span_mapped(divp, divp))
        return 0;

    u8 joy_pressed = *(vu8 *)(hram + HRAM_JOY_PRESSED_OFF);
    u8 joy_held = *(vu8 *)(hram + HRAM_JOY_HELD_OFF);
    u8 add = *(vu8 *)(hram + HRAM_ADD_OFF);
    u8 sub = *(vu8 *)(hram + HRAM_SUB_OFF);
    u8 frame = *(vu8 *)(hram + HRAM_FRAME_OFF);
    u8 div = *(vu8 *)divp;
    u8 species = *(vu8 *)(wram + OFF_ENEMY_SPECIES);
    u8 opponent = *(vu8 *)(wram + OFF_OPPONENT);
    u8 battle = *(vu8 *)(wram + OFF_BATTLE_STATE);
    u8 level = *(vu8 *)(wram + OFF_ENEMY_LEVEL);
    u16 dv = ((u16)*(vu8 *)(wram + OFF_ENEMY_DV0) << 8)
           | (u16)*(vu8 *)(wram + OFF_ENEMY_DV1);
    u8 low_health = *(vu8 *)(wram + OFF_LOW_HEALTH);
    u8 snd5 = *(vu8 *)(wram + OFF_SOUND_CH5);
    u8 snd6 = *(vu8 *)(wram + OFF_SOUND_CH6);
    u8 snd7 = *(vu8 *)(wram + OFF_SOUND_CH7);
    u8 snd8 = *(vu8 *)(wram + OFF_SOUND_CH8);
    u32 phys_keys = get_current_keys();

    u16 pc_a = 0;
    u16 pc_s = 0;
    if (query_span_mapped(PC_A_ADDR, PC_A_ADDR + 1u))
    {
        pc_a = *(vu16 *)PC_A_ADDR;
        live_status |= 1u << 4;
    }
    if (query_span_mapped(PC_S_ADDR, PC_S_ADDR + 1u))
    {
        pc_s = *(vu16 *)PC_S_ADDR;
        live_status |= 1u << 5;
    }

    live_wram = wram;
    live_hram = hram;
    live_div_ptr = divp;
    live_joy_pressed = joy_pressed;
    live_joy_held = joy_held;
    live_rng = ((u32)add << 16) | ((u32)sub << 8) | frame;
    live_div = div;
    live_raw_dv = dv;
    live_status |= 0x07u;
    if (battle == 0x01 && opponent == 0x83 && species == 0x83 && level == 0x46)
        live_status |= 1u << 3;

    DvTraceEntry e = {
        .seq = ++trace_seq,
        .wram = wram,
        .hram = hram,
        .div_ptr = divp,
        .phys_keys = phys_keys,
        .rng = ((u16)add << 8) | sub,
        .raw_dv = dv,
        .pc_a = pc_a,
        .pc_s = pc_s,
        .div = div,
        .frame = frame,
        .joy_pressed = joy_pressed,
        .joy_held = joy_held,
        .species = species,
        .opponent = opponent,
        .battle = battle,
        .level = level,
        .low_health = low_health,
        .snd5 = snd5,
        .snd6 = snd6,
        .snd7 = snd7,
        .snd8 = snd8,
    };
    trace_buf[trace_seq & TRACE_MASK] = e;

    if (armed)
    {
        if (opponent_seq == 0 && opponent == 0x83)
            opponent_seq = trace_seq;

        if ((low_health & 0x80u) != 0)
            lowhealth_bit7_seen = true;

        bool audio_now = wait_audio_active(e);
        DvTraceEntry prev = entry_at(trace_seq - 1u);
        bool audio_prev = prev.seq != 0 && wait_audio_active(prev);
        if (audio_start_seq == 0 && audio_now && !audio_prev)
            audio_start_seq = trace_seq;
        if (audio_start_seq != 0 && audio_end_seq == 0 && !audio_now && audio_prev)
            audio_end_seq = trace_seq;

        if (dvwrite_seq == 0 && trace_seq > trigger_seq && dv != baseline_dv &&
            (species == 0x83 || opponent == 0x83))
        {
            dvwrite_seq = trace_seq;
            dvwrite_entry = e;
            pre_entry = entry_at(trace_seq - 1u);
        }
    }

    return live_status;
}

void host_blue_dvtrace_mark_physical_a(void)
{
    if (trace_seq != 0)
        physical_a_seq = trace_seq;
}

void host_blue_dvtrace_mark_game_a(void)
{
    if (trace_seq != 0)
        game_a_seq = trace_seq;
}

void host_blue_dvtrace_set_arm_source(u32 source)
{
    pending_arm_source = source;
}

u32 host_blue_dvtrace_arm(void)
{
    if ((live_status & 0x07u) != 0x07u || trace_seq == 0)
        return 0;

    armed = true;
    active_arm_source = pending_arm_source;
    pending_arm_source = ARM_SOURCE_UNKNOWN;
    trigger_seq = trace_seq;
    trigger_entry = entry_at(trigger_seq);
    baseline_dv = (u16)live_raw_dv;

    opponent_seq = 0;
    audio_start_seq = 0;
    audio_end_seq = 0;
    lowhealth_bit7_seen = (trigger_entry.low_health & 0x80u) != 0;
    dvwrite_seq = battle_seq = 0;
    memset(&dvwrite_entry, 0, sizeof(dvwrite_entry));
    memset(&pre_entry, 0, sizeof(pre_entry));
    memset(&battle_entry, 0, sizeof(battle_entry));
    save_slot = save_error = 0;
    add2_matches = false;
    return trigger_seq;
}

u32 host_blue_dvtrace_finalize(void)
{
    if (!armed || trace_seq == 0)
        return 0;

    battle_seq = trace_seq;
    battle_entry = entry_at(battle_seq);
    u16 dv = battle_entry.raw_dv;
    u8 hi = (u8)(dv >> 8);
    u8 lo = (u8)dv;
    d2_c0 = (u8)(hi - lo);
    d2_c1 = (u8)(d2_c0 - 1u);
    add2_matches = ((u8)(battle_entry.rng >> 8) == hi);

    save_csv();
    armed = false;
    return battle_seq;
}

u32 host_blue_dvtrace_seq(void) { return trace_seq; }
u32 host_blue_dvtrace_status(void) { return live_status; }
u32 host_blue_dvtrace_rng(void) { return live_rng; }
u32 host_blue_dvtrace_div(void) { return live_div; }
u32 host_blue_dvtrace_raw_dv(void) { return live_raw_dv; }
u32 host_blue_dvtrace_wram(void) { return live_wram; }
u32 host_blue_dvtrace_hram(void) { return live_hram; }
u32 host_blue_dvtrace_div_ptr(void) { return live_div_ptr; }
u32 host_blue_dvtrace_joy_pressed(void) { return live_joy_pressed; }
u32 host_blue_dvtrace_joy_held(void) { return live_joy_held; }
u32 host_blue_dvtrace_arm_source(void) { return active_arm_source; }
u32 host_blue_dvtrace_trigger_seq(void) { return trigger_seq; }
u32 host_blue_dvtrace_physical_a_seq(void) { return physical_a_seq; }
u32 host_blue_dvtrace_game_a_seq(void) { return game_a_seq; }
u32 host_blue_dvtrace_opponent_seq(void) { return opponent_seq; }
u32 host_blue_dvtrace_audio_start_seq(void) { return audio_start_seq; }
u32 host_blue_dvtrace_audio_end_seq(void) { return audio_end_seq; }
u32 host_blue_dvtrace_dvwrite_seq(void) { return dvwrite_seq; }
u32 host_blue_dvtrace_battle_seq(void) { return battle_seq; }
u32 host_blue_dvtrace_save_slot(void) { return save_slot; }
u32 host_blue_dvtrace_save_error(void) { return save_error; }
