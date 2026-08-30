#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL
#define WRAM_SLOT 0x0021B6CCu
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u

#define OFF_ENEMY_SPECIES 0x0FCCu
#define OFF_ENEMY_DV0     0x0FD8u
#define OFF_ENEMY_DV1     0x0FD9u
#define OFF_ENEMY_LEVEL   0x0FDAu
#define OFF_BATTLE_STATE  0x1034u
#define OFF_OPPONENT      0x1036u

// HRAM base is FF80.
#define HRAM_JOY_PRESSED_OFF 0x33u  // FFB3
#define HRAM_JOY_HELD_OFF    0x34u  // FFB4
#define HRAM_ADD_OFF         0x53u  // FFD3
#define HRAM_SUB_OFF         0x54u  // FFD4
#define HRAM_FRAME_OFF       0x55u  // FFD5

#define TRACE_LEN 256u
#define TRACE_MASK (TRACE_LEN - 1u)

// arm_source values written to CSV.
#define ARM_SOURCE_UNKNOWN 0u
#define ARM_SOURCE_GAME_A  1u
#define ARM_SOURCE_EXACT2F 2u

typedef struct
{
    u32 seq;
    u32 wram;
    u32 hram;
    u32 div_ptr;
    u16 rng;
    u16 raw_dv;
    u8 div;
    u8 frame;
    u8 joy_pressed;
    u8 joy_held;
    u8 species;
    u8 opponent;
    u8 battle;
    u8 level;
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
static bool two_call_ok = false;
static u8 solve_c1 = 0;
static u8 solve_c2 = 0;
static u8 solve_q1 = 0;
static u8 solve_q2 = 0;
static u8 solve_d1 = 0;
static u8 solve_d2 = 0;
static u8 solve_gap = 0;

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

static void write_bytes(Handle file, u64 *offset, const char *s, u32 len)
{
    u32 written = 0;
    if (R_SUCCEEDED(FSFILE_Write(file, &written, *offset, s, len, 0)))
        *offset += written;
}

static void solve_last_two_calls(DvTraceEntry before, DvTraceEntry after, u16 dv)
{
    two_call_ok = false;
    solve_c1 = solve_c2 = solve_q1 = solve_q2 = 0;
    solve_d1 = solve_d2 = solve_gap = 0;

    if (before.seq == 0 || after.seq == 0)
        return;

    u8 a0 = (u8)(before.rng >> 8);
    u8 s0 = (u8)before.rng;
    u8 out2 = (u8)(dv >> 8); // CFD8 = second BattleRandom output
    u8 out1 = (u8)dv;        // CFD9 = first BattleRandom output
    u8 s2_target = (u8)after.rng;

    for (u8 c1 = 0; c1 <= 1u; c1++)
    {
        u8 d1 = (u8)(out1 - a0 - c1);
        u16 sum1 = (u16)a0 + (u16)d1 + (u16)c1;
        u8 carry1 = sum1 > 0xFFu ? 1u : 0u;

        for (u8 c2 = 0; c2 <= 1u; c2++)
        {
            u8 d2 = (u8)(out2 - out1 - c2);
            u16 sum2 = (u16)out1 + (u16)d2 + (u16)c2;
            u8 carry2 = sum2 > 0xFFu ? 1u : 0u;
            u8 gap = (u8)(d2 - d1);
            if (gap > 4u)
                continue;

            for (u8 q1 = 0; q1 <= 1u; q1++)
            {
                u8 s1 = (u8)(s0 - (u8)(d1 + q1) - carry1);
                for (u8 q2 = 0; q2 <= 1u; q2++)
                {
                    u8 s2 = (u8)(s1 - (u8)(d2 + q2) - carry2);
                    if (s2 == s2_target)
                    {
                        two_call_ok = true;
                        solve_c1 = c1;
                        solve_c2 = c2;
                        solve_q1 = q1;
                        solve_q2 = q2;
                        solve_d1 = d1;
                        solve_d2 = d2;
                        solve_gap = gap;
                        return;
                    }
                }
            }
        }
    }
}

static void write_meta_row(Handle file, u64 *off)
{
    char line[1024];
    u32 trigger_to_battle = battle_seq >= trigger_seq ? battle_seq - trigger_seq : 0u;
    u32 dvwrite_lag = battle_seq >= dvwrite_seq && dvwrite_seq != 0u ? battle_seq - dvwrite_seq : 0u;
    int n = snprintf(
        line, sizeof(line),
        "meta,version,title_id,arm_source,trigger_seq,battle_seq,trigger_to_battle,dvwrite_seq,dvwrite_lag,raw_dv,shiny,baseline_dv,"
        "wram,hram,div_ptr,trigger_rng_add,trigger_rng_sub,trigger_frame,trigger_div,trigger_joy_pressed,trigger_joy_held,"
        "pre_rng_add,pre_rng_sub,pre_frame,pre_div,pre_joy_pressed,pre_joy_held,"
        "dvwrite_rng_add,dvwrite_rng_sub,dvwrite_frame,dvwrite_div,dvwrite_joy_pressed,dvwrite_joy_held,"
        "battle_rng_add,battle_rng_sub,battle_frame,battle_div,battle_joy_pressed,battle_joy_held,"
        "d2_c0,d2_c1,add2_match,two_call_ok,c1,c2,q1,q2,d1,d2,gap\n"
        "MEWTWO,6,%016llX,%lu,%lu,%lu,%lu,%lu,%lu,%04X,%u,%04X,"
        "%08lX,%08lX,%08lX,%02X,%02X,%02X,%02X,%02X,%02X,"
        "%02X,%02X,%02X,%02X,%02X,%02X,"
        "%02X,%02X,%02X,%02X,%02X,%02X,"
        "%02X,%02X,%02X,%02X,%02X,%02X,"
        "%02X,%02X,%u,%u,%u,%u,%u,%u,%02X,%02X,%u\n",
        (unsigned long long)BLUE_JP_TITLE_ID,
        (unsigned long)active_arm_source,
        (unsigned long)trigger_seq,
        (unsigned long)battle_seq,
        (unsigned long)trigger_to_battle,
        (unsigned long)dvwrite_seq,
        (unsigned long)dvwrite_lag,
        (unsigned int)battle_entry.raw_dv,
        shiny_from_raw(battle_entry.raw_dv) ? 1u : 0u,
        (unsigned int)baseline_dv,
        (unsigned long)battle_entry.wram,
        (unsigned long)battle_entry.hram,
        (unsigned long)battle_entry.div_ptr,
        (u8)(trigger_entry.rng >> 8), (u8)trigger_entry.rng, trigger_entry.frame, trigger_entry.div,
        trigger_entry.joy_pressed, trigger_entry.joy_held,
        (u8)(pre_entry.rng >> 8), (u8)pre_entry.rng, pre_entry.frame, pre_entry.div,
        pre_entry.joy_pressed, pre_entry.joy_held,
        (u8)(dvwrite_entry.rng >> 8), (u8)dvwrite_entry.rng, dvwrite_entry.frame, dvwrite_entry.div,
        dvwrite_entry.joy_pressed, dvwrite_entry.joy_held,
        (u8)(battle_entry.rng >> 8), (u8)battle_entry.rng, battle_entry.frame, battle_entry.div,
        battle_entry.joy_pressed, battle_entry.joy_held,
        d2_c0, d2_c1, add2_matches ? 1u : 0u, two_call_ok ? 1u : 0u,
        solve_c1, solve_c2, solve_q1, solve_q2, solve_d1, solve_d2, solve_gap);
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
        "seq,rel,rng_add,rng_sub,frame,div,raw_dv,joy_pressed,joy_held,species,opponent,battle,level,wram,hram,div_ptr,"
        "is_trigger,is_pre,is_dvwrite,is_battle\n";
    write_bytes(file, &off, hdr, (u32)strlen(hdr));

    u32 first = trigger_seq > 8u ? trigger_seq - 8u : 1u;
    u32 last = battle_seq;
    if (last - first >= TRACE_LEN)
        first = last - TRACE_LEN + 1u;

    char line[384];
    for (u32 seq = first; seq <= last; seq++)
    {
        DvTraceEntry e = entry_at(seq);
        if (e.seq == 0)
            continue;
        s32 rel = (s32)e.seq - (s32)trigger_seq;
        int n = snprintf(
            line, sizeof(line),
            "%lu,%ld,%02X,%02X,%02X,%02X,%04X,%02X,%02X,%02X,%02X,%02X,%02X,%08lX,%08lX,%08lX,%u,%u,%u,%u\n",
            (unsigned long)e.seq, (long)rel,
            (u8)(e.rng >> 8), (u8)e.rng, e.frame, e.div, e.raw_dv,
            e.joy_pressed, e.joy_held, e.species, e.opponent, e.battle, e.level,
            (unsigned long)e.wram, (unsigned long)e.hram, (unsigned long)e.div_ptr,
            e.seq == trigger_seq, e.seq == pre_entry.seq,
            e.seq == dvwrite_seq, e.seq == battle_seq);
        if (n > 0)
            write_bytes(file, &off, line, (u32)n);
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
    if (!query_span_mapped(wram + OFF_ENEMY_SPECIES, wram + OFF_OPPONENT) ||
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

    live_wram = wram;
    live_hram = hram;
    live_div_ptr = divp;
    live_joy_pressed = joy_pressed;
    live_joy_held = joy_held;
    live_rng = ((u32)add << 16) | ((u32)sub << 8) | frame;
    live_div = div;
    live_raw_dv = dv;
    live_status = 0x07u;
    if (battle == 0x01 && opponent == 0x83 && species == 0x83 && level == 0x46)
        live_status |= 1u << 3;

    DvTraceEntry e = {
        .seq = ++trace_seq,
        .wram = wram,
        .hram = hram,
        .div_ptr = divp,
        .rng = ((u16)add << 8) | sub,
        .raw_dv = dv,
        .div = div,
        .frame = frame,
        .joy_pressed = joy_pressed,
        .joy_held = joy_held,
        .species = species,
        .opponent = opponent,
        .battle = battle,
        .level = level,
    };
    trace_buf[trace_seq & TRACE_MASK] = e;

    if (armed && dvwrite_seq == 0 && trace_seq > trigger_seq && dv != baseline_dv &&
        (species == 0x83 || opponent == 0x83))
    {
        dvwrite_seq = trace_seq;
        dvwrite_entry = e;
        pre_entry = entry_at(trace_seq - 1u);
    }

    return live_status;
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
    dvwrite_seq = battle_seq = 0;
    memset(&dvwrite_entry, 0, sizeof(dvwrite_entry));
    memset(&pre_entry, 0, sizeof(pre_entry));
    memset(&battle_entry, 0, sizeof(battle_entry));
    save_slot = save_error = 0;
    two_call_ok = false;
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

    DvTraceEntry after = dvwrite_entry.seq ? dvwrite_entry : battle_entry;
    if (pre_entry.seq)
        solve_last_two_calls(pre_entry, after, dv);

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
u32 host_blue_dvtrace_dvwrite_seq(void) { return dvwrite_seq; }
u32 host_blue_dvtrace_battle_seq(void) { return battle_seq; }
u32 host_blue_dvtrace_dvwrite_rng(void) { return ((u32)(u8)(dvwrite_entry.rng >> 8) << 16) | ((u32)(u8)dvwrite_entry.rng << 8) | dvwrite_entry.frame; }
u32 host_blue_dvtrace_dvwrite_div(void) { return dvwrite_entry.div; }
u32 host_blue_dvtrace_pre_rng(void) { return ((u32)(u8)(pre_entry.rng >> 8) << 16) | ((u32)(u8)pre_entry.rng << 8) | pre_entry.frame; }
u32 host_blue_dvtrace_pre_div(void) { return pre_entry.div; }
u32 host_blue_dvtrace_d2_pair(void) { return ((u32)d2_c0 << 8) | d2_c1; }
u32 host_blue_dvtrace_add2_match(void) { return add2_matches ? 1u : 0u; }
u32 host_blue_dvtrace_two_call_ok(void) { return two_call_ok ? 1u : 0u; }
u32 host_blue_dvtrace_solve(void) { return ((u32)solve_d1 << 24) | ((u32)solve_d2 << 16) | ((u32)solve_gap << 8) | ((u32)solve_c1 << 3) | ((u32)solve_c2 << 2) | ((u32)solve_q1 << 1) | solve_q2; }
u32 host_blue_dvtrace_save_slot(void) { return save_slot; }
u32 host_blue_dvtrace_save_error(void) { return save_error; }
