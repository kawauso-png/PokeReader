from pathlib import Path

c = Path('3gx/sources/main.c').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()

required = [
    'if (suicune_exact2_release_waiting())',
    'const u32 wanted = 14U;',
    'suicune_phase_slot = wanted;',
    'suicune_phase_target_tick = target;',
    'while (svcGetSystemTick() < target) { }',
    'suicune_phase_actual_tick = svcGetSystemTick();',
    'suicune_obs_up_release_tick = now;',
    'suicune_obs_resume_tick = suicune_phase_actual_tick;',
    'suicune_obs_wait_resume_hook = true;',
]
for s in required:
    if s not in c:
        raise SystemExit(f'v767j missing: {s}')

# The v7.6.7i low-level Exact2 authority must remain intact.
h = Path('reader_core/src/crystal/hook.rs').read_text()
if 'let low_up = (joy[JOY_HJOYPAD_DOWN] & PAD_UP) != 0;' not in h:
    raise SystemExit('v767j lost FFA4 Exact2 authority')
if 'EXACT2_RELEASE_WAITING = true;' not in h or 'pnp::request_pause();' not in h:
    raise SystemExit('v767j lost two-poll pause handshake')

# Scope guard: the new M14 block may only schedule Resume; it must not mutate
# HID/GB joypad/RNG/DIV/DV state or synthesize UP.
a = c.index('// v7.6.7j: after FFA4 proved two UP polls')
b = c.index('        if (suicune_release_resume_pending)', a)
block = c[a:b]
for bad in [
    'hid_up_mask_begin', 'hid_up_mask_apply', 'host_write_mem', 'gb_mem',
    'RNG_ADVANCE', 'DIV', '| KEY_DUP', 'KEY_DUP |', 'rJOYP', '0xff00'
]:
    if bad in block:
        raise SystemExit(f'v767j forbidden in resume block: {bad}')

if t.count('V767J') < 5:
    raise SystemExit('v767j CSV lineage markers missing')

print('AUDIT PASS: v7.6.7j retains FFA4 Exact2 and phase-locks only Pause/Resume at M14')
print('AUDIT PASS: release/target/actual/first-hook telemetry is enabled without input/RNG/DIV mutation')
