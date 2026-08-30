#include <3ds.h>
#include "title_info.h"

#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL
#define BLUE_HRAM_SLOT 0x0021B6DCu

// Japanese Red/Blue HRAM layout (base FF80):
// hJoyPressed = FFB3 -> +0x33
// hJoyHeld    = FFB4 -> +0x34
#define HJOY_PRESSED_OFF 0x33u
#define HJOY_HELD_OFF    0x34u
#define GAME_A_MASK      0x01u

static bool a_latched = false;
static u32 last_pressed = 0;
static u32 last_held = 0;

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

u32 host_blue_game_a_edge(void)
{
    last_pressed = 0;
    last_held = 0;

    if (get_title_id() != BLUE_JP_TITLE_ID)
        return 0;
    if (!query_span_mapped(BLUE_HRAM_SLOT, BLUE_HRAM_SLOT + 3u))
        return 0;

    u32 hram = *(vu32 *)BLUE_HRAM_SLOT;
    if (!query_span_mapped(hram + HJOY_PRESSED_OFF, hram + HJOY_HELD_OFF))
        return 0;

    last_pressed = *(vu8 *)(hram + HJOY_PRESSED_OFF);
    last_held = *(vu8 *)(hram + HJOY_HELD_OFF);

    // Release in the game's own joypad state clears the latch. This makes the
    // second A after the Mewtwo cry a distinct edge even when the 3DS-side HID
    // edge is missed by the overlay sampling cadence.
    if ((last_held & GAME_A_MASK) == 0)
        a_latched = false;

    if ((last_pressed & GAME_A_MASK) != 0 && !a_latched)
    {
        a_latched = true;
        return 1;
    }

    return 0;
}

u32 host_blue_game_joy_pressed(void) { return last_pressed; }
u32 host_blue_game_joy_held(void) { return last_held; }
