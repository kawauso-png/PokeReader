#!/usr/bin/env python3
from pathlib import Path
s=Path('3gx/sources/main.c').read_text()
start=s.find('// v7.2.4 robust diagnostic arm.')
end=s.find('// Y + right / Y + left', start)
if start<0 or end<0:
    raise SystemExit('v724 audit: robust arm block missing')
arm=s[start:end]
req=[
    '(held & KEY_B) && (held & KEY_DUP)',
    '!fixed_run_pending && !suicune_auto_resume_pending',
    'arm_suicune_probe();',
    'fixed_run_pending = true;',
    'suicune_auto_resume_pending = true;',
]
for x in req:
    if x not in arm: raise SystemExit('v724 audit missing: '+x)
if 'just_pressed & KEY_B' in arm:
    raise SystemExit('v724 audit: fragile B edge still used')
# The release gate must exclude UP but include B, so B never leaks into Exact2F.
if 'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)' not in s:
    raise SystemExit('v724 audit: B release gate missing')
if 'fixed_frames_remaining = fixed_a_frames;' not in s:
    raise SystemExit('v724 audit: Exact2F scheduling missing')
if 'if ((held & (KEY_DUP | KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)' not in s:
    raise SystemExit('v724 audit: UP release auto-resume gate missing')
print('v7.2.4 robust probe arm audit PASS')
