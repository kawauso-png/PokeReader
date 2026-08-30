#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL

// Hardware-recovered update-version-1 host-state slots.
#define WRAM_SLOT 0x0021B6CCu
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u

// The historical runtime kept LR35902 PC exactly 0xCC bytes before the WRAM
// pointer slot (0022F5FC -> 0022F6C8).  WRAM/HRAM preserved their structure
// relationship after the update-version-1 layout move, so Stage 8 tests the
// corresponding current-runtime candidate without using it for control flow.
#define PC_SLOT   0x0021B600u
#define MAP_PC    0xA1C8u

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

static u32 pc_value = 0;
static u32 pc_changes = 0;
static u32 pc_samples = 0;
static u32 map_pc_hits = 0;
static u32 map_hit_sample = 0;
static u32 map_rng_pack = 0;
static u32 map_div_value = 0;
static u16 prev_pc = 0;
static bool have_prev_pc = false;

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

u32 host_blue_stage8_sample(void)
{
    status = 0;
    wram = 0;
    hram = 0;
    div_host = 0;
    rng_pack = 0;
    div_value = 0;
    raw_dv = 0;
    pc_value = 0;

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

    // Observational PC probe.  This candidate is never used to hook or alter
    // execution in Stage 8; it is only sampled and compared to the historical
    // map-frame PC 0xA1C8 seen on hardware.
    if (query_span_mapped(PC_SLOT, PC_SLOT + 1u))
    {
        u16 pc = *(vu16 *)PC_SLOT;
        pc_value = pc;
        pc_samples++;
        status |= 1u << 4;

        if (have_prev_pc && pc != prev_pc)
            pc_changes++;
        prev_pc = pc;
        have_prev_pc = true;

        if (pc == MAP_PC)
        {
            map_pc_hits++;
            map_hit_sample = pc_samples;
            map_rng_pack = rng_pack;
            map_div_value = div_value;
        }
    }

    return status;
}

u32 host_blue_stage8_wram_slot(void) { return WRAM_SLOT; }
u32 host_blue_stage8_hram_slot(void) { return HRAM_SLOT; }
u32 host_blue_stage8_div_slot(void) { return DIV_SLOT; }
u32 host_blue_stage8_wram(void) { return wram; }
u32 host_blue_stage8_hram(void) { return hram; }
u32 host_blue_stage8_div_host(void) { return div_host; }
u32 host_blue_stage8_rng_pack(void) { return rng_pack; }
u32 host_blue_stage8_div_value(void) { return div_value; }
u32 host_blue_stage8_raw_dv(void) { return raw_dv; }
u32 host_blue_stage8_div_changes(void) { return div_changes; }
u32 host_blue_stage8_div_steps(void) { return div_steps; }

u32 host_blue_stage8_pc_slot(void) { return PC_SLOT; }
u32 host_blue_stage8_pc(void) { return pc_value; }
u32 host_blue_stage8_pc_changes(void) { return pc_changes; }
u32 host_blue_stage8_pc_samples(void) { return pc_samples; }
u32 host_blue_stage8_map_pc(void) { return MAP_PC; }
u32 host_blue_stage8_map_hits(void) { return map_pc_hits; }
u32 host_blue_stage8_map_hit_sample(void) { return map_hit_sample; }
u32 host_blue_stage8_map_rng_pack(void) { return map_rng_pack; }
u32 host_blue_stage8_map_div_value(void) { return map_div_value; }
