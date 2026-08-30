#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL
#define HOST_SCAN_MIN 0x00200000u
#define HOST_SCAN_MAX 0x00400000u
#define CANDIDATE_MIN 0x08000000u
#define CANDIDATE_MAX 0x14000000u
#define PAGE_SIZE 0x1000u
#define PAGES_PER_STEP 4u

#define OFF_ENEMY_SPECIES 0x0FCCu
#define OFF_ENEMY_DV_ATK_DEF 0x0FD8u
#define OFF_ENEMY_DV_SPE_SPC 0x0FD9u
#define OFF_ENEMY_LEVEL 0x0FDAu
#define OFF_BATTLE_STATE 0x1034u
#define OFF_OPPONENT 0x1036u

static u32 probe_cursor = HOST_SCAN_MIN;
static u32 probe_passes = 0;
static u32 probe_hits = 0;
static u32 probe_found_source = 0;
static u32 probe_found_base = 0;
static u32 probe_found_dv = 0;
static u32 probe_last_candidate = 0;

static bool query_span_mapped(u32 start, u32 end)
{
    MemInfo info;
    PageInfo page;
    if (svcQueryMemory(&info, &page, start) != 0)
        return false;
    if (info.state == MEMSTATE_FREE || info.state == MEMSTATE_RESERVED)
        return false;
    if (start < info.base_addr)
        return false;
    u32 offset = start - info.base_addr;
    if (offset >= info.size)
        return false;
    return end >= start && (end - info.base_addr) < info.size;
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

    if (*(vu8 *)(base + OFF_ENEMY_SPECIES) != 0x83)
        return false;
    if (*(vu8 *)(base + OFF_ENEMY_LEVEL) != 0x46)
        return false;
    if (*(vu8 *)(base + OFF_OPPONENT) != 0x83)
        return false;
    if (*(vu8 *)(base + OFF_BATTLE_STATE) != 0x01)
        return false;

    probe_found_dv = ((u32)*(vu8 *)(base + OFF_ENEMY_DV_ATK_DEF) << 8)
                   | (u32)*(vu8 *)(base + OFF_ENEMY_DV_SPE_SPC);
    return true;
}

u32 host_blue_probe_step(void)
{
    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;
    if (probe_found_base != 0)
        return probe_found_base;

    for (u32 page_index = 0; page_index < PAGES_PER_STEP && probe_found_base == 0; page_index++)
    {
        if (probe_cursor >= HOST_SCAN_MAX)
        {
            probe_cursor = HOST_SCAN_MIN;
            probe_passes++;
            probe_hits = 0;
        }

        u32 page_start = probe_cursor;
        u32 page_end = page_start + PAGE_SIZE - 1;
        if (page_end >= HOST_SCAN_MAX)
            page_end = HOST_SCAN_MAX - 1;

        if (query_span_mapped(page_start, page_end))
        {
            for (u32 src = page_start; src + 3 <= page_end; src += 4)
            {
                u32 candidate = *(vu32 *)src;
                if (candidate < CANDIDATE_MIN || candidate >= CANDIDATE_MAX)
                    continue;

                probe_hits++;
                probe_last_candidate = candidate;

                if (mewtwo_fingerprint(candidate))
                {
                    probe_found_source = src;
                    probe_found_base = candidate;
                    break;
                }
            }
        }

        probe_cursor = page_start + PAGE_SIZE;
    }

    return probe_found_base;
}

u32 host_blue_probe_cursor(void) { return probe_cursor; }
u32 host_blue_probe_passes(void) { return probe_passes; }
u32 host_blue_probe_hits(void) { return probe_hits; }
u32 host_blue_probe_source(void) { return probe_found_source; }
u32 host_blue_probe_candidate(void) { return probe_found_base != 0 ? probe_found_base : probe_last_candidate; }
u32 host_blue_probe_dv(void) { return probe_found_dv; }
