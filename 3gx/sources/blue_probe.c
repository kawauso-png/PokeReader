#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL

#define WRAM_SLOT 0x0021B6CCu
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u

// Stage 9 direct signature scan found A1C8 once at 0021B8F8 and C8A1 at
// 0021B890. Stage 10 removes the expensive page scan and samples these two
// halfwords every host frame to determine whether either behaves like LR35902
// PC rather than coincidental data.
#define PC_A_ADDR 0x0021B8F8u
#define PC_S_ADDR 0x0021B890u
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
    u16 value;
    u16 prev;
    u32 samples;
    u32 changes;
    u32 rom_range;
    u32 map_hits;
    bool have_prev;
} PcProbe;

static PcProbe probe_a = {0};
static PcProbe probe_s = {0};

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

static void sample_pc_probe(u32 addr, u16 signature, PcProbe *p)
{
    if (!query_span_mapped(addr, addr + 1u))
        return;

    u16 v = *(vu16 *)addr;
    p->value = v;
    p->samples++;

    if (p->have_prev && v != p->prev)
        p->changes++;
    p->prev = v;
    p->have_prev = true;

    // The Japanese Blue ROM executes primarily from 0000-7FFF.  This is not
    // sufficient by itself to prove a PC, but combined with a high per-frame
    // change rate and A1C8 recurrence it is a useful discriminator.
    if (v <= 0x7FFFu)
        p->rom_range++;
    if (v == signature)
        p->map_hits++;
}

u32 host_blue_stage10_sample(void)
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
            {
                status |= 1u << 3;
            }
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

    sample_pc_probe(PC_A_ADDR, MAP_PC, &probe_a);
    sample_pc_probe(PC_S_ADDR, MAP_PC_SWAP, &probe_s);
    if (probe_a.samples != 0)
        status |= 1u << 4;
    if (probe_s.samples != 0)
        status |= 1u << 5;

    return status;
}

u32 host_blue_stage10_wram(void) { return wram; }
u32 host_blue_stage10_hram(void) { return hram; }
u32 host_blue_stage10_div_host(void) { return div_host; }
u32 host_blue_stage10_rng_pack(void) { return rng_pack; }
u32 host_blue_stage10_div_value(void) { return div_value; }
u32 host_blue_stage10_raw_dv(void) { return raw_dv; }
u32 host_blue_stage10_div_changes(void) { return div_changes; }
u32 host_blue_stage10_div_steps(void) { return div_steps; }

u32 host_blue_stage10_a_addr(void) { return PC_A_ADDR; }
u32 host_blue_stage10_a_value(void) { return probe_a.value; }
u32 host_blue_stage10_a_samples(void) { return probe_a.samples; }
u32 host_blue_stage10_a_changes(void) { return probe_a.changes; }
u32 host_blue_stage10_a_rom(void) { return probe_a.rom_range; }
u32 host_blue_stage10_a_hits(void) { return probe_a.map_hits; }

u32 host_blue_stage10_s_addr(void) { return PC_S_ADDR; }
u32 host_blue_stage10_s_value(void) { return probe_s.value; }
u32 host_blue_stage10_s_samples(void) { return probe_s.samples; }
u32 host_blue_stage10_s_changes(void) { return probe_s.changes; }
u32 host_blue_stage10_s_rom(void) { return probe_s.rom_range; }
u32 host_blue_stage10_s_hits(void) { return probe_s.map_hits; }
