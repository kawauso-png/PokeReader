#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL

// Hardware-recovered update-version-1 host-state layout.
#define KNOWN_WRAM_SOURCE 0x0021B6CCu
#define HRAM_SLOT         0x0021B6DCu
#define PRED_DIV_SLOT     0x0021B798u

#define OFF_ENEMY_SPECIES 0x0FCCu
#define OFF_ENEMY_LEVEL   0x0FDAu
#define OFF_BATTLE_STATE  0x1034u
#define OFF_OPPONENT      0x1036u

#define HRAM_RANDOM_ADD_OFF 0x53u
#define HRAM_RANDOM_SUB_OFF 0x54u
#define HRAM_FRAME_OFF      0x55u

// Stage 5 showed PRED_DIV_SLOT contains a small value (0x0000000F) rather than
// a readable pointer. Probe a tight neighborhood for both possible layouts:
//   1) rDIV stored inline in the low byte of a host-state field;
//   2) a nearby field still stores a pointer to the rDIV byte.
#define DIV_SCAN_MIN (PRED_DIV_SLOT - 0x80u)
#define DIV_SCAN_MAX (PRED_DIV_SLOT + 0x80u)
#define DIV_SCAN_COUNT (((DIV_SCAN_MAX - DIV_SCAN_MIN) / 4u) + 1u)

static u8 inline_prev[DIV_SCAN_COUNT];
static u8 inline_have[DIV_SCAN_COUNT];
static u32 inline_changes[DIV_SCAN_COUNT];
static u32 inline_div_steps[DIV_SCAN_COUNT];
static u8 inline_delta[DIV_SCAN_COUNT];

static u8 ptr_prev[DIV_SCAN_COUNT];
static u8 ptr_have[DIV_SCAN_COUNT];
static u32 ptr_changes[DIV_SCAN_COUNT];
static u32 ptr_div_steps[DIV_SCAN_COUNT];
static u8 ptr_delta[DIV_SCAN_COUNT];
static u32 ptr_target[DIV_SCAN_COUNT];

static u32 stage6_status = 0;
static u32 stage6_samples = 0;
static u32 stage6_wram = 0;
static u32 stage6_hram = 0;
static u32 stage6_rng_pack = 0;

static u32 stage6_pred_raw = 0;
static u8 stage6_pred_value = 0;
static u32 stage6_pred_changes = 0;
static u32 stage6_pred_steps = 0;
static u8 stage6_pred_delta = 0;

static u32 best_inline_src = 0;
static u8 best_inline_value = 0;
static u32 best_inline_changes = 0;
static u32 best_inline_steps = 0;
static u8 best_inline_delta = 0;

static u32 best_ptr_src = 0;
static u32 best_ptr_target = 0;
static u8 best_ptr_value = 0;
static u32 best_ptr_changes = 0;
static u32 best_ptr_steps = 0;
static u8 best_ptr_delta = 0;

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

static bool mewtwo_fingerprint(u32 base)
{
    const u32 addrs[] = {
        base + OFF_ENEMY_SPECIES,
        base + OFF_ENEMY_LEVEL,
        base + OFF_OPPONENT,
        base + OFF_BATTLE_STATE,
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

static bool div_like_delta(u8 delta)
{
    // GB DIV advances about 18 ticks per ~59.7 Hz video frame. Allow a little
    // timing jitter while keeping this distinct from ordinary +1 counters.
    return delta >= 14u && delta <= 22u;
}

static void update_series(u8 value, u8 *prev, u8 *have, u32 *changes,
                          u32 *steps, u8 *delta_out)
{
    if (*have)
    {
        u8 delta = (u8)(value - *prev);
        *delta_out = delta;
        if (value != *prev)
            (*changes)++;
        if (div_like_delta(delta))
            (*steps)++;
    }
    *prev = value;
    *have = 1;
}

u32 host_blue_stage6_sample(void)
{
    stage6_status = 0;
    stage6_wram = 0;
    stage6_hram = 0;
    stage6_rng_pack = 0;

    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;

    if (!query_span_mapped(KNOWN_WRAM_SOURCE, KNOWN_WRAM_SOURCE + 3u))
        return 0;
    stage6_status |= 1u << 0;
    stage6_wram = *(vu32 *)KNOWN_WRAM_SOURCE;

    if (mewtwo_fingerprint(stage6_wram))
        stage6_status |= 1u << 1;

    if (query_span_mapped(HRAM_SLOT, HRAM_SLOT + 3u))
    {
        stage6_status |= 1u << 2;
        stage6_hram = *(vu32 *)HRAM_SLOT;
        if (query_span_mapped(stage6_hram + HRAM_RANDOM_ADD_OFF,
                              stage6_hram + HRAM_FRAME_OFF))
        {
            u8 add = *(vu8 *)(stage6_hram + HRAM_RANDOM_ADD_OFF);
            u8 sub = *(vu8 *)(stage6_hram + HRAM_RANDOM_SUB_OFF);
            u8 frame = *(vu8 *)(stage6_hram + HRAM_FRAME_OFF);
            stage6_rng_pack = ((u32)add << 16) | ((u32)sub << 8) | frame;
            stage6_status |= 1u << 3;
        }
    }

    if (!query_span_mapped(DIV_SCAN_MIN, DIV_SCAN_MAX + 3u))
        return stage6_status;
    stage6_status |= 1u << 4;
    stage6_samples++;

    best_inline_src = 0;
    best_inline_value = 0;
    best_inline_changes = 0;
    best_inline_steps = 0;
    best_inline_delta = 0;
    best_ptr_src = 0;
    best_ptr_target = 0;
    best_ptr_value = 0;
    best_ptr_changes = 0;
    best_ptr_steps = 0;
    best_ptr_delta = 0;

    for (u32 i = 0; i < DIV_SCAN_COUNT; i++)
    {
        u32 src = DIV_SCAN_MIN + i * 4u;
        u32 raw = *(vu32 *)src;
        u8 inline_value = (u8)raw;
        update_series(inline_value, &inline_prev[i], &inline_have[i],
                      &inline_changes[i], &inline_div_steps[i], &inline_delta[i]);

        if (inline_div_steps[i] > best_inline_steps ||
            (inline_div_steps[i] == best_inline_steps && inline_changes[i] > best_inline_changes))
        {
            best_inline_src = src;
            best_inline_value = inline_value;
            best_inline_changes = inline_changes[i];
            best_inline_steps = inline_div_steps[i];
            best_inline_delta = inline_delta[i];
        }

        // Pointer candidates are deliberately range-limited before querying.
        if (raw >= 0x08000000u && raw < 0x14000000u && query_byte_mapped(raw))
        {
            u8 value = *(vu8 *)raw;
            ptr_target[i] = raw;
            update_series(value, &ptr_prev[i], &ptr_have[i],
                          &ptr_changes[i], &ptr_div_steps[i], &ptr_delta[i]);

            if (ptr_div_steps[i] > best_ptr_steps ||
                (ptr_div_steps[i] == best_ptr_steps && ptr_changes[i] > best_ptr_changes))
            {
                best_ptr_src = src;
                best_ptr_target = raw;
                best_ptr_value = value;
                best_ptr_changes = ptr_changes[i];
                best_ptr_steps = ptr_div_steps[i];
                best_ptr_delta = ptr_delta[i];
            }
        }
    }

    u32 pred_i = (PRED_DIV_SLOT - DIV_SCAN_MIN) / 4u;
    stage6_pred_raw = *(vu32 *)PRED_DIV_SLOT;
    stage6_pred_value = (u8)stage6_pred_raw;
    stage6_pred_changes = inline_changes[pred_i];
    stage6_pred_steps = inline_div_steps[pred_i];
    stage6_pred_delta = inline_delta[pred_i];

    return stage6_status;
}

u32 host_blue_stage6_samples(void) { return stage6_samples; }
u32 host_blue_stage6_wram(void) { return stage6_wram; }
u32 host_blue_stage6_hram(void) { return stage6_hram; }
u32 host_blue_stage6_rng_pack(void) { return stage6_rng_pack; }

u32 host_blue_stage6_pred_slot(void) { return PRED_DIV_SLOT; }
u32 host_blue_stage6_pred_raw(void) { return stage6_pred_raw; }
u32 host_blue_stage6_pred_value(void) { return stage6_pred_value; }
u32 host_blue_stage6_pred_changes(void) { return stage6_pred_changes; }
u32 host_blue_stage6_pred_steps(void) { return stage6_pred_steps; }
u32 host_blue_stage6_pred_delta(void) { return stage6_pred_delta; }

u32 host_blue_stage6_best_inline_src(void) { return best_inline_src; }
u32 host_blue_stage6_best_inline_value(void) { return best_inline_value; }
u32 host_blue_stage6_best_inline_changes(void) { return best_inline_changes; }
u32 host_blue_stage6_best_inline_steps(void) { return best_inline_steps; }
u32 host_blue_stage6_best_inline_delta(void) { return best_inline_delta; }

u32 host_blue_stage6_best_ptr_src(void) { return best_ptr_src; }
u32 host_blue_stage6_best_ptr_target(void) { return best_ptr_target; }
u32 host_blue_stage6_best_ptr_value(void) { return best_ptr_value; }
u32 host_blue_stage6_best_ptr_changes(void) { return best_ptr_changes; }
u32 host_blue_stage6_best_ptr_steps(void) { return best_ptr_steps; }
u32 host_blue_stage6_best_ptr_delta(void) { return best_ptr_delta; }
