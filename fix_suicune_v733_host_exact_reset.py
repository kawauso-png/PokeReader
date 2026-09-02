#!/usr/bin/env python3
from pathlib import Path

M = Path('3gx/sources/main.c')
s = M.read_text()

old = '''void host_request_resume(void)
{
    is_paused = false;
    fixed_frames_remaining = 0;
    fixed_run_pending = false;
}
'''
new = '''void host_request_resume(void)
{
    // v7.3.3: a VC software reset must also reset the C-side Exact2F state.
    // Rust v7.3.1/v7.3.2 already wipes RNG/SCAN state, but these host statics
    // live outside Rust and otherwise survive the VC reset. A stale
    // suicune_auto_resume_pending=true is especially bad: the pause loop
    // handles that block before the UP+B trigger, so holding UP can trap the
    // next TEST in the old run's release-wait state and B is never examined.
    is_paused = false;
    fixed_frames_remaining = 0;
    fixed_run_pending = false;
    fixed_armed = false;
    suicune_auto_resume_pending = false;
    fixed_a_frames = 2;
    fixed_last_run = 0;
}
'''
if s.count(old) != 1:
    raise SystemExit(f'v733 host_request_resume anchor count {s.count(old)}')
s = s.replace(old, new, 1)

# Safety: keep fixed_run_id monotonic. Rust synchronizes last_run_id after a
# reset, so resetting the ID itself would create unnecessary ambiguity.
resume = s[s.index('void host_request_resume(void)'):]
resume = resume[:resume.index('}\n')+2]
for marker in [
    'fixed_frames_remaining = 0;',
    'fixed_run_pending = false;',
    'fixed_armed = false;',
    'suicune_auto_resume_pending = false;',
    'fixed_a_frames = 2;',
    'fixed_last_run = 0;',
]:
    if marker not in resume:
        raise SystemExit('v733 missing reset marker: ' + marker)
if 'fixed_run_id = 0;' in resume:
    raise SystemExit('v733 must not reset fixed_run_id')

# The proven physical trigger remains untouched.
if s.count('(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)') != 1:
    raise SystemExit('v733 UP+B trigger missing/duplicated')
if 'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)' not in s:
    raise SystemExit('v733 B-release pre-Exact2F gate missing')
if 'suicune_auto_resume_pending && !(held & KEY_DUP)' not in s:
    raise SystemExit('v733 Exact2F UP safety guard missing')

M.write_text(s)
print('Applied Suicune v7.3.3 host Exact2F reset: stale auto-resume/armed/pending state cleared on VC reset; UP+B protocol unchanged')
