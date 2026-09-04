from pathlib import Path


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT E FAIL: missing {label}: {needle!r}')


def forbid(text, needle, label):
    if needle in text:
        raise SystemExit(f'AUDIT E FAIL: forbidden {label}: {needle!r}')

h = Path('reader_core/src/crystal/hook.rs').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()
main = Path('3gx/sources/main.c').read_text()

# Observation-only baseline: the live block must contain no HID mask/restore
# write calls. Existing C helper definitions may remain compiled but unused.
live_a = h.index('// ---- v7.6.7 continuous physical-UP HID mask probe')
live_b = h.index('// Diagnostics for the legacy cycle hook', live_a)
live = h[live_a:live_b]
forbid(live, 'pnp::hid_mask_up_begin()', 'HID mask begin in live baseline')
forbid(live, 'pnp::hid_mask_up_restore()', 'HID restore in live baseline')
need(live, 'let capable = true;', 'read-only arm')
need(live, 'no-mask baseline', 'baseline marker')

# Continuous B -> release -> physical UP flow is unchanged.
stage_a = main.index('if (suicune_wait_up_after_b)')
stage_b = main.index('// Y+L schedules a fixed run', stage_a)
stage = main[stage_a:stage_b]
need(stage, 'if (held & KEY_DUP)', 'physical UP gate')
need(stage, 'is_paused = false;', 'continuous resume')
forbid(stage, 'fixed_run_pending = true;', 'old Exact2F handoff')

# Both views are observed once per advance. Gen2 PAD_UP is bit 6, matching the
# host Dup bit used by PokeReader.
need(h, 'pub fn live_pass_observe_hjoypad_down(hjoy: u8, host_keys: u32)', 'dual observer')
need(h, 'const PAD_UP: u8 = 0x40;', 'Crystal UP bit')
need(h, 'const HOST_UP: u32 = 0x40;', 'host UP bit')
need(h, 'host_observed_advances', 'host observed counter')
need(h, 'host_up_advances', 'host UP counter')
need(t, 'live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a), pnp::current_keys());', 'dual sample call')
need(t, 'LIVEPASS,V767E,', 'V767E main line')
need(t, 'LIVEPASSHOST,V767E,', 'V767E host line')

# Keep the exact 22-frame segmentation from c/d so comparisons are apples to
# apples even though no masking occurs in e.
need(h, 'const LIVE_MASK_FRAMES: u32 = 16;', '16F nominal pre window')
need(h, 'const LIVE_PASS_FRAMES: u32 = 2;', '2F nominal pass window')
need(h, 'const LIVE_POST_FRAMES: u32 = 4;', '4F nominal post window')
need(h, 'LIVE_PASS.pass_end_advance.wrapping_add(LIVE_POST_FRAMES - 1)', '22F stop')

# Still no game/RNG/DIV writes in the live block.
forbid(live, 'RNG_ADVANCE =', 'RNG mutation')
forbid(live, 'ADIV =', 'ADIV mutation')
forbid(live, 'SDIV =', 'SDIV mutation')
forbid(live, 'gb_mem::write', 'GB memory mutation')

print('AUDIT E PASS: observation-only continuous-UP baseline; no HID writes')
print('AUDIT E PASS: host key bit and Crystal FF9A sampled side by side for 22 advances')
