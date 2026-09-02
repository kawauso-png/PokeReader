#!/usr/bin/env python3
from pathlib import Path
import re

M=Path('3gx/sources/main.c')
s=M.read_text()

# v7.3.4: the old FastValidate trigger used just_pressed, but the pause loop
# normally polls every 50 ms. A normal short B tap can occur entirely between
# polls and vanish. Use B level while UP is held; fixed_run_pending immediately
# latches the run and then waits for B release, so one held B cannot retrigger.
old='(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)'
new='(held & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)'
if s.count(old)!=1:
    raise SystemExit(f'v734 UP+B edge trigger count {s.count(old)}')
s=s.replace(old,new,1)

# While UP is physically held at a paused TEST, poll at 1 ms instead of the
# legacy 50 ms. This makes a normal short B tap observable. Keep the 50 ms idle
# poll when UP is not held. Importantly, do NOT change the existing
# fixed_run_pending B-release wait or Exact2F timing path; those are already
# validated by the historical UP+B traces.
pat=re.compile(r'(u32 resume_keys = fixed_armed \? \(KEY_START \| KEY_R\) : \(KEY_A \| KEY_START \| KEY_R\);.*?if \(just_pressed & resume_keys\).*?\}\s*)(svcSleepThread\(50000000\);)',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('v734 final pause idle sleep anchor not found')
replacement=m.group(1)+'''// v7.3.4: once UP is held for Suicune TEST, sample B at 1 kHz.
        // The VC remains frozen here; B-release gating and Exact2F are unchanged.
        if (held & KEY_DUP)
        {
            svcSleepThread(1000000);
        }
        else
        {
            svcSleepThread(50000000);
        }'''
s=s[:m.start()]+replacement+s[m.end():]

# Safety/regression checks.
if s.count(new)!=1:
    raise SystemExit('v734 level trigger missing/duplicated')
if old in s:
    raise SystemExit('v734 stale edge trigger')
if 'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)' not in s:
    raise SystemExit('v734 pre-Exact2F B-release gate missing')
if 'svcSleepThread(10000000);' not in s:
    raise SystemExit('v734 proven 10ms pending/release polling unexpectedly changed')
if 'suicune_auto_resume_pending && !(held & KEY_DUP)' not in s:
    raise SystemExit('v734 exact-UP safety guard missing')
if 'if (held & KEY_DUP)' not in replacement or 'svcSleepThread(1000000);' not in replacement:
    raise SystemExit('v734 fast UP poll missing')

M.write_text(s)
print('Applied Suicune v7.3.4 UP+B Robust: level-latched B trigger + 1ms UP wait polling; proven B-release/Exact2F timing unchanged')
