#!/usr/bin/env python3
from pathlib import Path
M=Path('3gx/sources/main.c').read_text()

def need(x,m,label):
    if m not in x: raise SystemExit('v734 missing '+label+': '+m)
def forbid(x,m,label):
    if m in x: raise SystemExit('v734 forbidden '+label+': '+m)

# B is level-latched while physical UP is held. This intentionally avoids
# dependence on a 50ms just_pressed edge.
need(M,'(held & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)','level-latched UP+B trigger')
forbid(M,'(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)','stale edge-only UP+B trigger')

# The run remains frozen until B is released, so level-triggering cannot leak B
# into a VC frame or retrigger the run.
need(M,'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)','B release gate')
need(M,'fixed_run_pending = true;','pending latch')
need(M,'fixed_frames_remaining = fixed_a_frames;','Exact2F start after release')
need(M,'fixed_a_frames = 2;','Exact2F length')
need(M,'suicune_auto_resume_pending && !(held & KEY_DUP)','UP required during exact frames')
need(M,'svcSleepThread(10000000);','proven 10ms pending/release wait preserved')

# Only the pre-trigger UP-held wait is fast-polled; normal idle pause remains
# 50ms. This fixes detection without modifying the proven Exact2F timing path.
need(M,'if (held & KEY_DUP)','UP fast-poll branch')
need(M,'svcSleepThread(1000000);','1ms trigger poll')
need(M,'svcSleepThread(50000000);','normal 50ms idle poll')

# v7.3.3 host reset fix must remain in the chain.
need(M,'fixed_armed = false;','host armed reset')
need(M,'suicune_auto_resume_pending = false;','host auto-resume reset')

print('v7.3.4 AUDIT PASS: UP+B level-latched, pre-trigger UP wait at 1ms, proven 10ms B-release/Exact2F path preserved, host reset preserved')
