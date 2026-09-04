from pathlib import Path


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT G FAIL: missing {label}: {needle!r}')


def forbid(text, needle, label):
    if needle in text:
        raise SystemExit(f'AUDIT G FAIL: forbidden {label}: {needle!r}')

hid = Path('3gx/sources/hid.c').read_text()
main = Path('3gx/sources/main.c').read_text()
trace = Path('reader_core/src/crystal/trace.rs').read_text()
hook = Path('reader_core/src/crystal/hook.rs').read_text()

# Keep the known v7.6.7d live mask architecture and continuous B->UP resume.
need(hid, 'u32 pa = svcConvertVAToPA((const void *)g_key_addr, false);', 'physical translation capability')
need(main, 'if (!suicune_live_pass_ready)', 'capability gate')
stage_a = main.index('if (suicune_wait_up_after_b)')
stage_b = main.index('// Y+L schedules a fixed run', stage_a)
stage = main[stage_a:stage_b]
forbid(stage, 'hid_up_mask_begin()', 'paused mask write')
forbid(stage, 'hid_up_mask_restore()', 'paused restore write')
need(stage, 'is_paused = false;', 'continuous resume')
need(hook, 'if requested != RJOYP_ADDR', 'rJOYP-only guard')
need(hook, 'pnp::hid_mask_up_begin()', 'hook-timed mask begin')
need(hook, 'live_pass_restore_previous_mask();', 'next-hook restore')
need(hook, 'const LIVE_MASK_FRAMES: u32 = 16;', '16F mask')
need(hook, 'const LIVE_PASS_FRAMES: u32 = 2;', '2F pass')
need(hook, 'const LIVE_POST_FRAMES: u32 = 4;', '4F remask')

# Correct JP VC Crystal consumer map. Old FF98/FF9A verifier must be absent.
for addr in range(0xffa2, 0xffaa):
    need(trace, f'gb_mem::read_u8(0x{addr:04x})', f'joy byte {addr:04X}')
forbid(trace, 'gb_mem::read_u8(0xff9a)', 'old FF9A verifier')
forbid(trace, 'gb_mem::read_u8(0xff98)', 'old FF98 verifier')
need(hook, 'let hjoy = joy[JOY_HJOY_DOWN];', 'FFA8 authoritative game level')
need(hook, 'const JOY_HJOY_DOWN: usize = 6;', 'FFA8 index')

# Host and raw joypad samples are observation-only and bounded to 22 advances.
need(hook, 'const LIVE_SAMPLE_CAP: usize = 22;', 'bounded sample buffer')
need(hook, 'host_up_advances', 'host UP counter')
need(hook, 'joy_samples: [[u8; 8]; LIVE_SAMPLE_CAP]', 'raw joy samples')
need(trace, 'LIVEPASS,V767G,', 'main lineage')
need(trace, 'LIVEPASSHOST,V767G,', 'host lineage')
need(trace, 'JOYMAP,V767G,', 'joy aggregate lineage')
need(trace, 'JOYFRAME,V767G,', 'joy raw lineage')

# No game memory/RNG/DIV mutation added by g.
live_a = hook.index('// ---- v7.6.7 continuous physical-UP HID mask probe')
live_b = hook.index('// Diagnostics for the legacy cycle hook', live_a)
live = hook[live_a:live_b]
forbid(live, 'gb_mem::write', 'GB memory write')
forbid(live, 'RNG_ADVANCE =', 'RNG mutation')
forbid(live, 'ADIV =', 'ADIV mutation')
forbid(live, 'SDIV =', 'SDIV mutation')

print('AUDIT G PASS: v767d hook-timed mask/pass retained; no paused HID write')
print('AUDIT G PASS: JP joypad consumer map FFA2-FFA9 replaces old FF9A verifier')
print('AUDIT G PASS: host + raw 22-advance joy samples are bounded observation only')
