#!/usr/bin/env python3
from pathlib import Path
import re

M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
s=M.read_text(); t=T.read_text()

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

# Stamp the runtime UI/telemetry so the hardware build is unambiguous.
if 'S732 TEST UP+B' not in t or 'S732 SCAN' not in t or 'S732 RESET WAIT' not in t:
    raise SystemExit('v734 expected S732 UI baseline missing')
t=t.replace('S732 ', 'S734 ')
t=t.replace('GLOBALBEAM,V732', 'GLOBALBEAM,V734')
t=t.replace('SOFTRESET,V732', 'SOFTRESET,V734')

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
for x in ['S734 TEST UP+B','S734 SCAN','S734 RESET WAIT','GLOBALBEAM,V734','SOFTRESET,V734']:
    if x not in t: raise SystemExit('v734 missing UI/telemetry '+x)
if 'S732 ' in t:
    raise SystemExit('v734 stale S732 UI')

M.write_text(s); T.write_text(t)
print('Applied Suicune v7.3.4 UP+B Robust: level-latched B trigger + 1ms UP wait polling; proven B-release/Exact2F timing unchanged; S734 UI stamped')
