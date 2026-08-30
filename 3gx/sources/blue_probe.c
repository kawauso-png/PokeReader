#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL

// Hardware-recovered update-version-1 host-state slots.
#define WRAM_SLOT 0x0021B6CCu
#define HRAM_SLOT 0x0021B6DCu
#define DIV_SLOT  0x0021B7B4u

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

u32 host_blue_stage7_sample(void)
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

    return status;
}

u32 host_blue_stage7_wram_slot(void) { return WRAM_SLOT; }
u32 host_blue_stage7_hram_slot(void) { return HRAM_SLOT; }
u32 host_blue_stage7_div_slot(void) { return DIV_SLOT; }
u32 host_blue_stage7_wram(void) { return wram; }
u32 host_blue_stage7_hram(void) { return hram; }
u32 host_blue_stage7_div_host(void) { return div_host; }
u32 host_blue_stage7_rng_pack(void) { return rng_pack; }
u32 host_blue_stage7_div_value(void) { return div_value; }
u32 host_blue_stage7_raw_dv(void) { return raw_dv; }
u32 host_blue_stage7_div_changes(void) { return div_changes; }
u32 host_blue_stage7_div_steps(void) { return div_steps; }
