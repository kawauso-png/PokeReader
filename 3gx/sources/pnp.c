// PNP Compatibility file
// PNP uses wasm, so all functions are wasm compatible - hence the weirdness.

#include <3ds.h>
#include <string.h>
#include <stdio.h>
#include "ov.h"
#include "csvc.h"
#include "pnp.h"
#include "common.h"
#include "title_info.h"
#include "hid.h"

const u32 default_print_x = 8;
const u32 default_print_y = 10;
const u32 default_print_max_len = 30;

u32 print_x = default_print_x;
u32 print_y = default_print_y;
u32 print_max_len = default_print_max_len;
u64 game_start_ms = 0;

#define MAX_LINES 18
#define MAX_LINE_LENGTH 46
#define BLUE_JP_TITLE_ID 0x0004000000170E00ULL
#define BLUE_HOST_STATE_MIN 0x00200000u
#define BLUE_HOST_STATE_MAX 0x00400000u
#define BLUE_VC_BACKING_MIN 0x08B00000u
#define BLUE_VC_BACKING_MAX 0x08C00000u
#define BLUE_WRAM_PTR_SLOT 0x0022F6C8u
#define BLUE_HRAM_PTR_SLOT 0x0022F6D8u
#define BLUE_DIV_PTR_SLOT  0x0022F794u
#define BLUE_PTR_STABLE_SAMPLES 2u

typedef struct
{
  u32 slot;
  u32 last_candidate;
  u32 stable_samples;
} BlueStablePtr;

static BlueStablePtr blue_stable_ptrs[] = {
  { BLUE_WRAM_PTR_SLOT, 0, 0 },
  { BLUE_HRAM_PTR_SLOT, 0, 0 },
  { BLUE_DIV_PTR_SLOT,  0, 0 },
};

static bool query_resolves(u32 addr);
u32 host_blue_stable_ptr(u32 slot);

char print_buffer[MAX_LINES][MAX_LINE_LENGTH];
u32 print_buffer_color[MAX_LINES];
u32 buffer_index = 0;

void reset_print()
{
  print_x = default_print_x;
  print_y = default_print_y;
  print_max_len = default_print_max_len;
  memset(print_buffer, 0x00, MAX_LINES * MAX_LINE_LENGTH);
  memset(print_buffer_color, 0x00, MAX_LINES);
  buffer_index = 0;
}

void draw_to_screen(u32 screenId, u8 *framebuffer, u32 stride, u32 format)
{
  if (buffer_index == 0)
  {
    return;
  }

  ovDrawTranspartBlackRect((u32)framebuffer, stride, format, print_y, print_x, buffer_index * 12 + 4, print_max_len * 8 + 8, 1);

  print_x += 4;
  print_y += 4;

  for (u32 i = 0; i < buffer_index; i++)
  {
    u32 color = print_buffer_color[i];
    u32 red = (color >> 16) & 0xff;
    u32 green = (color >> 8) & 0xff;
    u32 blue = color & 0xff;
    ovDrawString((u32)framebuffer, stride, format, SCREEN_WIDTH, print_y, print_x, red, green, blue, print_buffer[i]);
    print_y += 12;
  }

  reset_print();
}

void host_print(u32 ptr, u32 size, u32 color)
{
  if (buffer_index < MAX_LINES)
  {
    u32 copy_size = (size < print_max_len - 1) ? size : print_max_len - 1;
    memcpy(print_buffer[buffer_index], (char *)ptr, copy_size);
    print_buffer[buffer_index][copy_size] = '\0';
    print_buffer_color[buffer_index] = color;
    buffer_index++;
  }
}

static char blue_ptr_label(u32 slot)
{
  if (slot == BLUE_WRAM_PTR_SLOT) return 'W';
  if (slot == BLUE_HRAM_PTR_SLOT) return 'H';
  if (slot == BLUE_DIV_PTR_SLOT) return 'D';
  return '?';
}

static void blue_print_raw_ptr_diag(u32 slot, u32 candidate)
{
  bool range_ok = candidate >= BLUE_VC_BACKING_MIN && candidate < BLUE_VC_BACKING_MAX;
  bool query_ok = range_ok && query_resolves(candidate);
  char line[32];
  int len = snprintf(line, sizeof(line), "RAW %c %08lX R%d Q%d",
                     blue_ptr_label(slot), (unsigned long)candidate,
                     range_ok ? 1 : 0, query_ok ? 1 : 0);
  if (len > 0)
  {
    host_print((u32)line, (u32)len, 0xFFFFFF);
  }
}

void host_read_mem(u32 game_addr, u32 size, u32 out_ptr)
{
  if (get_title_id() == BLUE_JP_TITLE_ID && size == sizeof(u32) &&
      (game_addr == BLUE_WRAM_PTR_SLOT || game_addr == BLUE_HRAM_PTR_SLOT || game_addr == BLUE_DIV_PTR_SLOT))
  {
    // Diagnostic read is limited to the three fixed 0x0022xxxx pointer slots.
    // The candidate is only displayed and classified; it is never dereferenced
    // unless host_blue_stable_ptr() independently validates and stabilizes it.
    u32 candidate = *(vu32 *)game_addr;
    blue_print_raw_ptr_diag(game_addr, candidate);

    // Never expose a raw VC backing pointer to Rust until the fixed slot has
    // produced the same valid candidate on two separate snapshot reads.
    // Returning zero makes resolve_ptr_slot() stop at mapped(0)==false, so no
    // backing address can be dereferenced during the unstable startup window.
    u32 stable = host_blue_stable_ptr(game_addr);
    memcpy((void *)out_ptr, &stable, sizeof(stable));
    return;
  }

  memcpy((void *)out_ptr, (void *)game_addr, size);
}

void host_write_mem(u32 game_addr, u32 size, u32 in_ptr)
{
  memcpy((void *)game_addr, (void *)in_ptr, size);
}

u32 host_just_pressed()
{
  return (get_previous_keys() ^ 0xffffffff) & get_current_keys();
}

u32 host_is_just_pressed(u32 io_bits)
{
  u32 just_pressed = host_just_pressed();
  bool is_just_pressed = (just_pressed & io_bits) != 0 && io_bits == get_current_keys();
  return (u32)is_just_pressed;
}

void host_set_print_max_len(u32 max_len)
{
  u32 max_len_with_terminator = max_len + 1;
  print_max_len = max_len_with_terminator > MAX_LINE_LENGTH ? MAX_LINE_LENGTH : max_len_with_terminator;
}

u64 host_get_game_title_id()
{
  return get_title_id();
}

void set_game_start_ms(u64 ms)
{
  game_start_ms = ms;
}

u64 host_game_start_ms()
{
  return game_start_ms;
}

u32 trampoline_addr = 0;
u32 route_hook_addr = 0;

void set_trampoline_addr(u32 trampoline) { trampoline_addr = trampoline; }
u32 get_trampoline_addr() { return trampoline_addr; }
void set_route_hook_addr(u32 route_hook) { route_hook_addr = route_hook; }
u32 get_route_hook_addr() { return route_hook_addr; }
u32 pa_from_va_ptr(u32 addr) { return (u32)PA_FROM_VA_PTR(addr); }

bool is_citra()
{
  s64 out = 0;
  svcGetSystemInfo(&out, 0x20000, 0);
  return out != 0;
}

static bool query_resolves(u32 addr)
{
  MemInfo info;
  PageInfo page;
  return svcQueryMemory(&info, &page, addr) == 0;
}

bool is_memory_mapped(u32 addr)
{
  if (addr == 0)
  {
    return false;
  }

  if (get_title_id() == BLUE_JP_TITLE_ID)
  {
    if (!((addr >= BLUE_HOST_STATE_MIN && addr < BLUE_HOST_STATE_MAX) ||
          (addr >= BLUE_VC_BACKING_MIN && addr < BLUE_VC_BACKING_MAX)))
    {
      return false;
    }
  }

  return query_resolves(addr);
}

u32 host_blue_stable_ptr(u32 slot)
{
  if (get_title_id() != BLUE_JP_TITLE_ID)
  {
    return 0;
  }

  BlueStablePtr *state = NULL;
  for (u32 i = 0; i < sizeof(blue_stable_ptrs) / sizeof(blue_stable_ptrs[0]); i++)
  {
    if (blue_stable_ptrs[i].slot == slot)
    {
      state = &blue_stable_ptrs[i];
      break;
    }
  }

  if (state == NULL || !query_resolves(slot))
  {
    return 0;
  }

  // This is the only raw pointer-slot read used for stabilization. The slot is
  // one of three fixed, hardware-validated 0x0022xxxx addresses; the candidate
  // itself is not dereferenced here.
  u32 candidate = *(vu32 *)slot;
  if (candidate < BLUE_VC_BACKING_MIN || candidate >= BLUE_VC_BACKING_MAX || !query_resolves(candidate))
  {
    state->last_candidate = 0;
    state->stable_samples = 0;
    return 0;
  }

  if (candidate == state->last_candidate)
  {
    if (state->stable_samples < BLUE_PTR_STABLE_SAMPLES)
    {
      state->stable_samples++;
    }
  }
  else
  {
    state->last_candidate = candidate;
    state->stable_samples = 1;
  }

  return state->stable_samples >= BLUE_PTR_STABLE_SAMPLES ? candidate : 0;
}
