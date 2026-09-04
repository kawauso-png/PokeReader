from pathlib import Path


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT D FAIL: missing {label}: {needle!r}')


def forbid(text, needle, label):
    if needle in text:
        raise SystemExit(f'AUDIT D FAIL: forbidden {label}: {needle!r}')

hid = Path('3gx/sources/hid.c').read_text()
main = Path('3gx/sources/main.c').read_text()
trace = Path('reader_core/src/crystal/trace.rs').read_text()
hook = Path('reader_core/src/crystal/hook.rs').read_text()

# Capability remains a hard gate; no blind 0x80000000 alias writes.
need(hid, 'u32 pa = svcConvertVAToPA((const void *)g_key_addr, false);', 'physical translation capability')
need(hid, 'return pa != 0;', 'capability result')
need(main, 'if (!suicune_live_pass_ready)', 'stage2 capability gate')

# The paused producer-race preflight must be gone.
forbid(main, '// v7.6.7 preflight occurs while still frozen.', 'old paused preflight')
stage_a = main.index('if (suicune_wait_up_after_b)')
stage_b = main.index('// Y+L schedules a fixed run', stage_a)
stage = main[stage_a:stage_b]
forbid(stage, 'hid_up_mask_begin()', 'paused mask write')
forbid(stage, 'hid_up_mask_restore()', 'paused restore write')
need(stage, 'is_paused = false;', 'continuous resume')

# Live hook still masks only immediately before rJOYP and restores on next hook.
need(hook, 'if requested != RJOYP_ADDR', 'rJOYP-only guard')
need(hook, 'pnp::hid_mask_up_begin()', 'hook-timed mask begin')
need(hook, 'live_pass_restore_previous_mask();', 'next-hook restore')

# Immediate verification is on the uncached physical alias only. The ordinary
# HID VA is producer-owned and Crystal FF9A is the authoritative consumer proof.
need(hid, 'if ((*pa & KEY_DUP) != 0)', 'PA-only clear verification')
need(hid, 'if (*old_pa != old_saved)', 'PA-only stacking restore verification')
need(hid, 'if (*pa != original)', 'PA-only failed-mask restore verification')
need(hid, 'if (*pa != saved)', 'PA-only normal restore verification')
forbid(hid, '|| *g_key_addr', 'dual-view equality gate')
forbid(hid, '| KEY_DUP', 'synthetic UP')

# Crystal-side proof remains mandatory and output lineage must be distinct.
need(trace, 'live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));', 'FF9A consumer proof')
need(trace, 'LIVEPASS,V767D,', 'V767D CSV stamp')
need(hook, 'const LIVE_MASK_FRAMES: u32 = 16;', '16F mask')
need(hook, 'const LIVE_PASS_FRAMES: u32 = 2;', '2F pass')
need(hook, 'const LIVE_POST_FRAMES: u32 = 4;', '4F remask')

print('AUDIT D PASS: no paused HID write-test; capability gate retained')
print('AUDIT D PASS: hook-timed rJOYP mask uses PA-only immediate check')
print('AUDIT D PASS: Crystal FF9A remains authoritative 16/2/4 consumer proof')
