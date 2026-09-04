from pathlib import Path


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT F FAIL: missing {label}: {needle!r}')


def forbid(text, needle, label):
    if needle in text:
        raise SystemExit(f'AUDIT F FAIL: forbidden {label}: {needle!r}')

h = Path('reader_core/src/crystal/hook.rs').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()
main = Path('3gx/sources/main.c').read_text()

# f remains a no-mask, read-only mapping probe. No HID/game/RNG mutation is
# allowed in the live block.
live_a = h.index('// ---- v7.6.7 continuous physical-UP HID mask probe')
live_b = h.index('// Diagnostics for the legacy cycle hook', live_a)
live = h[live_a:live_b]
forbid(live, 'pnp::hid_mask_up_begin()', 'HID mask begin')
forbid(live, 'pnp::hid_mask_up_restore()', 'HID restore')
forbid(live, 'RNG_ADVANCE =', 'RNG mutation')
forbid(live, 'ADIV =', 'ADIV mutation')
forbid(live, 'SDIV =', 'SDIV mutation')
forbid(live, 'gb_mem::write', 'GB memory mutation')
need(live, 'let capable = true;', 'read-only arm')

# Exact physical B -> release -> UP continuous flow remains unchanged.
stage_a = main.index('if (suicune_wait_up_after_b)')
stage_b = main.index('// Y+L schedules a fixed run', stage_a)
stage = main[stage_a:stage_b]
need(stage, 'if (held & KEY_DUP)', 'physical UP gate')
need(stage, 'is_paused = false;', 'continuous resume')
forbid(stage, 'fixed_run_pending = true;', 'old paused Exact2F handoff')

# Correct JP VC input map. The previous FF9A-only validator must be absent.
for addr in range(0xffa2, 0xffaa):
    need(t, f'gb_mem::read_u8(0x{addr:04x})', f'joy byte {addr:04X}')
for addr in range(0xff98, 0xffa0):
    forbid(t, f'gb_mem::read_u8(0x{addr:04x})', f'old wrong joy byte {addr:04X}')
need(h, 'const JOY_HJOYPAD_DOWN: usize = 2; // FFA4', 'low-level hJoypadDown map')
need(h, 'const JOY_HJOY_DOWN: usize = 6;    // FFA8', 'game hJoyDown map')
need(h, 'let hjoy = joy[JOY_HJOY_DOWN];', 'game counters use FFA8')
need(h, 'pub fn live_pass_observe_joymap(joy: [u8; 8], host_keys: u32)', 'joymap observer')

# Retain raw 22-advance samples, not only aggregates, so poll latency can be
# reconstructed without a second instrumented run.
need(h, 'const LIVE_SAMPLE_CAP: usize = 22;', '22-sample cap')
need(h, 'pub joy_samples: [[u8; 8]; LIVE_SAMPLE_CAP]', 'raw joy samples')
need(h, 'pub joy_sample_host: [u32; LIVE_SAMPLE_CAP]', 'raw host samples')
need(h, 'pub joy_first_up_rel: [u8; 8]', 'first-UP relative advances')
need(t, 'JOYMAP,V767F,', 'JOYMAP lineage')
need(t, 'JOYFRAME,V767F,', 'JOYFRAME lineage')
need(t, 'LIVEPASS,V767F,', 'LIVEPASS lineage')
need(t, 'LIVEPASSHOST,V767F,', 'LIVEPASSHOST lineage')

# Exact 22-frame observation window remains unchanged for comparability.
need(h, 'const LIVE_MASK_FRAMES: u32 = 16;', '16 nominal pre frames')
need(h, 'const LIVE_PASS_FRAMES: u32 = 2;', '2 nominal pass frames')
need(h, 'const LIVE_POST_FRAMES: u32 = 4;', '4 nominal post frames')

print('AUDIT F PASS: JP joypad map corrected to FFA2-FFA9; old FF98-FF9F validator absent')
print('AUDIT F PASS: read-only no-mask probe with 22 raw host+joy samples')
