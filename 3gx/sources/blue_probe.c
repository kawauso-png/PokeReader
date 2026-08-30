#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL

// Stage 4 hardware result on Japanese Blue update-version-1:
//   source slot 0x0021B6CC -> current C000/WRAM backing.
// Do not hard-code the backing address itself because it may move between boots.
#define KNOWN_WRAM_SOURCE 0x0021B6CCu

// In the old runtime the HRAM and DIV pointer slots were +0x10 and +0xCC from
// the WRAM slot respectively. Stage 5 tests whether that structure-relative
// layout survived even though the whole host-state structure moved.
#define HRAM_SLOT_DELTA 0x10u
#define DIV_SLOT_DELTA  0xCCu
#define HRAM_SLOT (KNOWN_WRAM_SOURCE + HRAM_SLOT_DELTA)
#define DIV_SLOT  (KNOWN_WRAM_SOURCE + DIV_SLOT_DELTA)

#define OFF_ENEMY_SPECIES 0x0FCCu
#define OFF_ENEMY_DV_ATK_DEF 0x0FD8u
#define OFF_ENEMY_DV_SPE_SPC 0x0FD9u
#define OFF_ENEMY_LEVEL 0x0FDAu
#define OFF_BATTLE_STATE 0x1034u
#define OFF_OPPONENT 0x1036u

// HRAM pointer semantics used by the old Blue implementation: base corresponds
// to GB FF80, so FFD3/FFD4/FFD5 are +0x53/+0x54/+0x55.
#define HRAM_RANDOM_ADD_OFF 0x53u
#define HRAM_RANDOM_SUB_OFF 0x54u
#define HRAM_FRAME_OFF      0x55u

static u32 stage5_status = 0;
static u32 stage5_wram = 0;
static u32 stage5_hram = 0;
static u32 stage5_div = 0;
static u32 stage5_rng_pack = 0;
static u32 stage5_div_value = 0;
static u32 stage5_frame_changes = 0;
static u32 stage5_div_changes = 0;
static u8 stage5_prev_frame = 0;
static u8 stage5_prev_div = 0;
static bool stage5_have_prev_frame = false;
static bool stage5_have_prev_div = false;

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
    u32 offset = start - info.base_addr;
    if (offset >= info.size)
        return false;
    return (end - info.base_addr) < info.size;
}

static bool query_byte_mapped(u32 addr)
{
    return query_span_mapped(addr, addr);
}

static bool mewtwo_fingerprint(u32 base)
{
    const u32 addrs[] = {
        base + OFF_ENEMY_SPECIES,
        base + OFF_ENEMY_LEVEL,
        base + OFF_OPPONENT,
        base + OFF_BATTLE_STATE,
        base + OFF_ENEMY_DV_ATK_DEF,
        base + OFF_ENEMY_DV_SPE_SPC,
    };

    for (u32 i = 0; i < sizeof(addrs) / sizeof(addrs[0]); i++)
    {
        if (!query_byte_mapped(addrs[i]))
            return false;
    }

    return *(vu8 *)(base + OFF_ENEMY_SPECIES) == 0x83
        && *(vu8 *)(base + OFF_ENEMY_LEVEL) == 0x46
        && *(vu8 *)(base + OFF_OPPONENT) == 0x83
        && *(vu8 *)(base + OFF_BATTLE_STATE) == 0x01;
}

u32 host_blue_stage5_sample(void)
{
    stage5_status = 0;
    stage5_wram = 0;
    stage5_hram = 0;
    stage5_div = 0;
    stage5_rng_pack = 0;
    stage5_div_value = 0;

    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;

    // bit 0: WRAM source slot itself is mapped/readable.
    if (!query_span_mapped(KNOWN_WRAM_SOURCE, KNOWN_WRAM_SOURCE + 3))
        return stage5_status;
    stage5_status |= 1u << 0;
    stage5_wram = *(vu32 *)KNOWN_WRAM_SOURCE;

    // bit 1: current WRAM pointer still resolves to the Mewtwo battle fingerprint.
    if (mewtwo_fingerprint(stage5_wram))
        stage5_status |= 1u << 1;

    // bit 2: predicted HRAM slot is mapped/readable.
    if (query_span_mapped(HRAM_SLOT, HRAM_SLOT + 3))
    {
        stage5_status |= 1u << 2;
        stage5_hram = *(vu32 *)HRAM_SLOT;

        // bit 3: predicted HRAM pointer exposes FFD3/FFD4/FFD5 bytes safely.
        if (query_span_mapped(stage5_hram + HRAM_RANDOM_ADD_OFF,
                              stage5_hram + HRAM_FRAME_OFF))
        {
            u8 add = *(vu8 *)(stage5_hram + HRAM_RANDOM_ADD_OFF);
            u8 sub = *(vu8 *)(stage5_hram + HRAM_RANDOM_SUB_OFF);
            u8 frame = *(vu8 *)(stage5_hram + HRAM_FRAME_OFF);
            stage5_rng_pack = ((u32)add << 16) | ((u32)sub << 8) | (u32)frame;
            stage5_status |= 1u << 3;

            if (stage5_have_prev_frame && frame != stage5_prev_frame)
                stage5_frame_changes++;
            stage5_prev_frame = frame;
            stage5_have_prev_frame = true;
        }
    }

    // bit 4: predicted DIV slot is mapped/readable.
    if (query_span_mapped(DIV_SLOT, DIV_SLOT + 3))
    {
        stage5_status |= 1u << 4;
        stage5_div = *(vu32 *)DIV_SLOT;

        // bit 5: predicted DIV pointer itself is readable.
        if (query_byte_mapped(stage5_div))
        {
            u8 div = *(vu8 *)stage5_div;
            stage5_div_value = div;
            stage5_status |= 1u << 5;

            if (stage5_have_prev_div && div != stage5_prev_div)
                stage5_div_changes++;
            stage5_prev_div = div;
            stage5_have_prev_div = true;
        }
    }

    return stage5_status;
}

u32 host_blue_stage5_wram_source(void) { return KNOWN_WRAM_SOURCE; }
u32 host_blue_stage5_wram(void) { return stage5_wram; }
u32 host_blue_stage5_hram_slot(void) { return HRAM_SLOT; }
u32 host_blue_stage5_hram(void) { return stage5_hram; }
u32 host_blue_stage5_div_slot(void) { return DIV_SLOT; }
u32 host_blue_stage5_div(void) { return stage5_div; }
u32 host_blue_stage5_rng_pack(void) { return stage5_rng_pack; }
u32 host_blue_stage5_div_value(void) { return stage5_div_value; }
u32 host_blue_stage5_frame_changes(void) { return stage5_frame_changes; }
u32 host_blue_stage5_div_changes(void) { return stage5_div_changes; }
