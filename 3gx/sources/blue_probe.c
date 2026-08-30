#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL

// Hardware-recovered update-version-1 host-state slots.
#define WRAM_SLOT 0x0021B6CCu
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u

// Stage 9 found direct A1C8/C8A1 signatures in this page. Hunt Lab keeps the
// two observed locations and also scans one 0x100-byte slice of the page per
// host frame, so a wrong candidate no longer needs a replacement build.
#define PC_SCAN_MIN 0x0021B000u
#define PC_SCAN_MAX 0x0021C000u
#define PC_SCAN_CHUNK 0x100u
#define PC_CANDIDATES 8u
#define PC_A_SEED 0x0021B8F8u
#define PC_S_SEED 0x0021B890u
#define MAP_PC 0xA1C8u
#define MAP_PC_SWAP 0xC8A1u

#define OFF_ENEMY_SPECIES 0x0FCCu
#define OFF_ENEMY_DV_ATK_DEF 0x0FD8u
#define OFF_ENEMY_DV_SPE_SPC 0x0FD9u
#define OFF_ENEMY_LEVEL 0x0FDAu
#define OFF_BATTLE_STATE 0x1034u
#define OFF_OPPONENT 0x1036u

#define HRAM_RANDOM_ADD_OFF 0x53u
#define HRAM_RANDOM_SUB_OFF 0x54u
#define HRAM_FRAME_OFF      0x55u

#define HIST_LEN 4096u
#define HIST_MASK (HIST_LEN - 1u)

static u32 status = 0;
static u32 wram = 0;
static u32 hram = 0;
static u32 div_host = 0;
static u32 rng_pack = 0;
static u32 div_value = 0;
static u32 raw_dv = 0;
static u32 div_changes = 0;
static u32 div_steps = 0;
static u8 prev_div = 0;
static bool have_prev_div = false;

typedef struct
{
    u32 addr;
    u16 value;
    u16 prev;
    u32 samples;
    u32 changes;
    u32 rom_range;
    u32 map_hits;
    u32 swap_hits;
    bool have_prev;
} PcCandidate;

static PcCandidate pc[PC_CANDIDATES] = {
    {.addr = PC_A_SEED},
    {.addr = PC_S_SEED},
};
static u32 pc_scan_cursor = PC_SCAN_MIN;
static u32 pc_scan_passes = 0;
static u32 pc_scan_sig_hits = 0;
static u32 best_pc_index = 0;

typedef struct
{
    u32 seq;
    u16 rng;
    u16 pc;
    u8 div;
    u8 frame;
    u8 flags;
    u8 pad;
} HistEntry;

static HistEntry history[HIST_LEN] = {{0}};
static u32 history_seq = 0;
static u32 history_count = 0;

static u32 rolling_zero = 0;
static u32 rolling_one = 0;
static u32 rolling_multi = 0;
static u32 rolling_phase_hist[16] = {0};
static u32 rolling_phase_mode = 0;
static u32 rolling_phase_mode_count = 0;

static u32 window_valid = 0;
static u32 window_frames = 0;
static u32 window_zero = 0;
static u32 window_one = 0;
static u32 window_multi = 0;
static u32 window_phase_mode = 0;
static u32 window_phase_count = 0;
static u32 window_map_hits = 0;
static u32 window_hash = 0;

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

static bool query_byte_mapped(u32 addr)
{
    return query_span_mapped(addr, addr);
}

static bool div_like_delta(u8 delta)
{
    return delta >= 14u && delta <= 22u;
}

static void add_pc_candidate(u32 addr)
{
    if (addr < PC_SCAN_MIN || addr + 1u >= PC_SCAN_MAX)
        return;
    for (u32 i = 0; i < PC_CANDIDATES; i++)
        if (pc[i].addr == addr)
            return;
    for (u32 i = 0; i < PC_CANDIDATES; i++)
    {
        if (pc[i].addr == 0)
        {
            pc[i].addr = addr;
            return;
        }
    }
}

static void scan_pc_slice(void)
{
    u32 start = pc_scan_cursor;
    u32 end = start + PC_SCAN_CHUNK;
    if (end > PC_SCAN_MAX)
        end = PC_SCAN_MAX;

    if (query_span_mapped(start, end - 1u))
    {
        for (u32 addr = start; addr + 1u < end; addr += 2u)
        {
            u16 v = *(vu16 *)addr;
            if (v == MAP_PC || v == MAP_PC_SWAP)
            {
                pc_scan_sig_hits++;
                add_pc_candidate(addr);
            }
        }
    }

    pc_scan_cursor += PC_SCAN_CHUNK;
    if (pc_scan_cursor >= PC_SCAN_MAX)
    {
        pc_scan_cursor = PC_SCAN_MIN;
        pc_scan_passes++;
    }
}

static void sample_pc_candidates(void)
{
    for (u32 i = 0; i < PC_CANDIDATES; i++)
    {
        PcCandidate *p = &pc[i];
        if (p->addr == 0 || !query_span_mapped(p->addr, p->addr + 1u))
            continue;
        u16 v = *(vu16 *)p->addr;
        p->value = v;
        p->samples++;
        if (p->have_prev && v != p->prev)
            p->changes++;
        p->prev = v;
        p->have_prev = true;
        if (v <= 0x7FFFu)
            p->rom_range++;
        if (v == MAP_PC)
            p->map_hits++;
        if (v == MAP_PC_SWAP)
            p->swap_hits++;
    }

    // Prefer recurring A1C8 first, then a PC-like ROM/change profile.  This is
    // only an observational score; Hunt Lab never patches execution via it.
    u32 best = 0;
    u32 best_score = 0;
    for (u32 i = 0; i < PC_CANDIDATES; i++)
    {
        PcCandidate *p = &pc[i];
        if (p->addr == 0 || p->samples == 0)
            continue;
        u32 change_pct = (p->changes * 100u) / p->samples;
        u32 rom_pct = (p->rom_range * 100u) / p->samples;
        u32 recurring = p->map_hits > 20u ? 200u : p->map_hits * 10u;
        u32 score = recurring + rom_pct + change_pct;
        if (score > best_score)
        {
            best_score = score;
            best = i;
        }
    }
    best_pc_index = best;
}

// Infer whether one ordinary Gen-I Random call can explain a sampled
// (hRandomAdd,hRandomSub) transition.  We try both possible incoming carries.
// A valid call must have its two rDIV reads no more than 2 ticks apart and the
// first read must lie inside the observed host-frame DIV interval (small guard
// margin included).  phase_out is the first-read position modulo 16.
static bool infer_one_call(HistEntry a, HistEntry b, u8 *phase_out)
{
    u8 a0 = (u8)(a.rng >> 8);
    u8 s0 = (u8)a.rng;
    u8 a1 = (u8)(b.rng >> 8);
    u8 s1 = (u8)b.rng;
    u8 span = (u8)(b.div - a.div);
    if (span > 40u)
        return false;

    bool found = false;
    u8 best_gap = 0xff;
    u8 best_pos = 0;
    for (u32 cin = 0; cin <= 1u; cin++)
    {
        u8 d1 = (u8)(a1 - a0 - (u8)cin);
        u16 sum = (u16)a0 + (u16)d1 + (u16)cin;
        u8 cout = sum > 0xffu ? 1u : 0u;
        u8 d2 = (u8)(s0 - s1 - cout);
        u8 gap = (u8)(d2 - d1);
        u8 pos = (u8)(d1 - a.div);
        if (gap <= 2u && pos <= (u8)(span + 3u))
        {
            if (!found || gap < best_gap)
            {
                found = true;
                best_gap = gap;
                best_pos = pos;
            }
        }
    }
    if (found && phase_out)
        *phase_out = best_pos & 0x0fu;
    return found;
}

static u32 phase_mode(const u32 *hist, u32 *count_out)
{
    u32 best = 0;
    u32 count = hist[0];
    for (u32 i = 1; i < 16u; i++)
    {
        if (hist[i] > count)
        {
            best = i;
            count = hist[i];
        }
    }
    if (count_out)
        *count_out = count;
    return best;
}

static void classify_transition(HistEntry a, HistEntry b, u32 *zero, u32 *one,
                                u32 *multi, u32 *phase_hist)
{
    if (a.rng == b.rng)
    {
        (*zero)++;
        return;
    }
    u8 ph = 0;
    if (infer_one_call(a, b, &ph))
    {
        (*one)++;
        phase_hist[ph]++;
    }
    else
    {
        (*multi)++;
    }
}

static void push_history(void)
{
    HistEntry e;
    e.seq = ++history_seq;
    e.rng = (u16)(rng_pack >> 8);
    e.pc = pc[best_pc_index].value;
    e.div = (u8)div_value;
    e.frame = (u8)rng_pack;
    e.flags = (u8)(status & 0xffu);
    e.pad = 0;

    if (history_count != 0)
    {
        HistEntry prev = history[(history_seq - 1u) & HIST_MASK];
        if (prev.seq == history_seq - 1u)
        {
            classify_transition(prev, e, &rolling_zero, &rolling_one,
                                &rolling_multi, rolling_phase_hist);
            rolling_phase_mode = phase_mode(rolling_phase_hist, &rolling_phase_mode_count);
        }
    }

    history[history_seq & HIST_MASK] = e;
    if (history_count < HIST_LEN)
        history_count++;
}

u32 host_blue_lab_sample(void)
{
    status = 0;
    wram = 0;
    hram = 0;
    div_host = 0;
    rng_pack = 0;
    div_value = 0;
    raw_dv = 0;

    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;

    if (query_span_mapped(WRAM_SLOT, WRAM_SLOT + 3u))
    {
        wram = *(vu32 *)WRAM_SLOT;
        if (query_span_mapped(wram + OFF_ENEMY_SPECIES, wram + OFF_OPPONENT))
        {
            status |= 1u << 0;
            raw_dv = ((u32)*(vu8 *)(wram + OFF_ENEMY_DV_ATK_DEF) << 8)
                   | (u32)*(vu8 *)(wram + OFF_ENEMY_DV_SPE_SPC);
            if (*(vu8 *)(wram + OFF_BATTLE_STATE) == 0x01 &&
                *(vu8 *)(wram + OFF_OPPONENT) == 0x83 &&
                *(vu8 *)(wram + OFF_ENEMY_SPECIES) == 0x83 &&
                *(vu8 *)(wram + OFF_ENEMY_LEVEL) == 0x46)
                status |= 1u << 3;
        }
    }

    if (query_span_mapped(HRAM_SLOT, HRAM_SLOT + 3u))
    {
        hram = *(vu32 *)HRAM_SLOT;
        if (query_span_mapped(hram + HRAM_RANDOM_ADD_OFF, hram + HRAM_FRAME_OFF))
        {
            u8 add = *(vu8 *)(hram + HRAM_RANDOM_ADD_OFF);
            u8 sub = *(vu8 *)(hram + HRAM_RANDOM_SUB_OFF);
            u8 frame = *(vu8 *)(hram + HRAM_FRAME_OFF);
            rng_pack = ((u32)add << 16) | ((u32)sub << 8) | frame;
            status |= 1u << 1;
        }
    }

    if (query_span_mapped(DIV_SLOT, DIV_SLOT + 3u))
    {
        div_host = *(vu32 *)DIV_SLOT;
        if (query_byte_mapped(div_host))
        {
            u8 div = *(vu8 *)div_host;
            div_value = div;
            status |= 1u << 2;
            if (have_prev_div)
            {
                u8 delta = (u8)(div - prev_div);
                if (div != prev_div)
                    div_changes++;
                if (div_like_delta(delta))
                    div_steps++;
            }
            prev_div = div;
            have_prev_div = true;
        }
    }

    scan_pc_slice();
    sample_pc_candidates();
    if (pc[best_pc_index].samples != 0)
        status |= 1u << 4;

    if ((status & 0x07u) == 0x07u)
        push_history();

    return status;
}

u32 host_blue_lab_analyze_window(u32 start_seq, u32 end_seq)
{
    window_valid = 0;
    window_frames = window_zero = window_one = window_multi = 0;
    window_phase_mode = window_phase_count = window_map_hits = 0;
    window_hash = 2166136261u;
    u32 ph[16] = {0};

    if (start_seq == 0 || end_seq <= start_seq || end_seq - start_seq >= HIST_LEN)
        return 0;
    HistEntry prev = history[start_seq & HIST_MASK];
    if (prev.seq != start_seq)
        return 0;

    for (u32 seq = start_seq + 1u; seq <= end_seq; seq++)
    {
        HistEntry cur = history[seq & HIST_MASK];
        if (cur.seq != seq)
            return 0;
        u32 z0 = window_zero, o0 = window_one, m0 = window_multi;
        classify_transition(prev, cur, &window_zero, &window_one, &window_multi, ph);
        u32 kind = window_zero != z0 ? 0u : (window_one != o0 ? 1u : (window_multi != m0 ? 2u : 3u));
        if (cur.pc == MAP_PC)
            window_map_hits++;
        window_hash ^= (kind & 3u) | ((u32)cur.div << 8) | ((u32)cur.frame << 16);
        window_hash *= 16777619u;
        prev = cur;
        window_frames++;
    }
    window_phase_mode = phase_mode(ph, &window_phase_count);
    window_valid = 1;
    return 1;
}

u32 host_blue_lab_wram(void) { return wram; }
u32 host_blue_lab_hram(void) { return hram; }
u32 host_blue_lab_div_host(void) { return div_host; }
u32 host_blue_lab_rng_pack(void) { return rng_pack; }
u32 host_blue_lab_div_value(void) { return div_value; }
u32 host_blue_lab_raw_dv(void) { return raw_dv; }
u32 host_blue_lab_div_changes(void) { return div_changes; }
u32 host_blue_lab_div_steps(void) { return div_steps; }

u32 host_blue_lab_seq(void) { return history_seq; }
u32 host_blue_lab_hist_count(void) { return history_count; }
u32 host_blue_lab_roll_zero(void) { return rolling_zero; }
u32 host_blue_lab_roll_one(void) { return rolling_one; }
u32 host_blue_lab_roll_multi(void) { return rolling_multi; }
u32 host_blue_lab_roll_phase(void) { return rolling_phase_mode; }
u32 host_blue_lab_roll_phase_n(void) { return rolling_phase_mode_count; }

u32 host_blue_lab_pc_addr(void) { return pc[best_pc_index].addr; }
u32 host_blue_lab_pc_value(void) { return pc[best_pc_index].value; }
u32 host_blue_lab_pc_samples(void) { return pc[best_pc_index].samples; }
u32 host_blue_lab_pc_changes(void) { return pc[best_pc_index].changes; }
u32 host_blue_lab_pc_rom(void) { return pc[best_pc_index].rom_range; }
u32 host_blue_lab_pc_map_hits(void) { return pc[best_pc_index].map_hits; }
u32 host_blue_lab_pc_swap_hits(void) { return pc[best_pc_index].swap_hits; }
u32 host_blue_lab_pc_scan_passes(void) { return pc_scan_passes; }
u32 host_blue_lab_pc_scan_hits(void) { return pc_scan_sig_hits; }

u32 host_blue_lab_window_valid(void) { return window_valid; }
u32 host_blue_lab_window_frames(void) { return window_frames; }
u32 host_blue_lab_window_zero(void) { return window_zero; }
u32 host_blue_lab_window_one(void) { return window_one; }
u32 host_blue_lab_window_multi(void) { return window_multi; }
u32 host_blue_lab_window_phase(void) { return window_phase_mode; }
u32 host_blue_lab_window_phase_n(void) { return window_phase_count; }
u32 host_blue_lab_window_map_hits(void) { return window_map_hits; }
u32 host_blue_lab_window_hash(void) { return window_hash; }
