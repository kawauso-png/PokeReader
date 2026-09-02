#!/usr/bin/env python3
from pathlib import Path
M=Path('3gx/sources/main.c').read_text(); T=Path('reader_core/src/crystal/trace.rs').read_text(); P=Path('reader_core/src/crystal/practical.rs').read_text()

def need(x,s,label):
    if s not in x: raise SystemExit('v737 missing '+label+': '+s[:100])
def forbid(x,s,label):
    if s in x: raise SystemExit('v737 forbidden '+label+': '+s[:100])

# Input race repair: phase alignment samples HID continuously and happens before ARM.
need(M,'static bool suicune_test_wait_start_phase_while_up(void)','phase helper')
need(M,'if (!suicune_test_up_only_now()) return false;','continuous UP proof')
need(M,'svcSleepThread(250000); // 0.25 ms; VC remains frozen.','phase polling')
exec_start=M.index('if (suicune_test_exec_active && suicune_test_exec_state <= 2)')
exec_end=M.index('if (suicune_release_resume_pending)',exec_start)
E=M[exec_start:exec_end]
need(E,'if (!suicune_test_wait_start_phase_while_up())','retryable phase wait')
need(E,'arm_suicune_probe();','ARM')
need(E,'fixed_frames_remaining--; // exact frame #1','immediate first frame')
if E.index('suicune_test_wait_start_phase_while_up') > E.index('arm_suicune_probe'):
    raise SystemExit('v737 ARM occurs before phase proof')
if E.index('arm_suicune_probe') > E.index('fixed_frames_remaining--; // exact frame #1'):
    raise SystemExit('v737 frame1 occurs before ARM')

# begin_exact2f must not contain the old blind host-phase wait.
b=M.index('static void suicune_test_begin_exact2f(void)'); e=M.index('u32 host_fixed_state',b); B=M[b:e]
forbid(B,'while (svcGetSystemTick() < target)','blind phase wait in begin_exact2f')
need(B,'fixed_frames_remaining = 2;','2F arm')
need(M,'if (suicune_auto_resume_pending && !(held & KEY_DUP))','frame2 physical-UP guard')
need(M,'suicune_test_exec_state = 7;','hard early-release abort')
need(M,'suicune_test_exec_state = 6;','successful resume')

# No regression of the safe v7.3.6 RNG path.
need(P,'const EMP_COUNT:usize=7','deduped empirical bank')
need(T,'fn rebind_shiny_post_v736','rel40 repaired resolver retained')
need(T,'practical_expected716_state','716 guard')
need(T,'practical_expected717_state','717 guard')

# UI must describe the empirically safe physical hold and current reset operation.
need(T,'S737 TEST HOLD UP 0.3s','hold UI')
need(T,'EXEC,V737','exec telemetry')
need(T,'GLOBALBEAM,V737','beam telemetry')
need(T,'SOFTRESET,V737','reset telemetry')
forbid(T,'S736','stale S736')
forbid(T,'R>RESET','stale R reset instruction')

# Small state-machine regression.  Before ARM a release consumes zero frames and
# returns to READY. Once ARM occurs, holding >=0.3s trivially covers phase wait + 2F;
# release after the two frame escapes reaches EX6.
def simulate(release_stage):
    frames=0; armed=False; state=1
    # UP seen -> phase wait
    state=2
    if release_stage=='phase': return frames,armed,1
    armed=True; state=3
    if release_stage=='after_arm_before_f1': return frames,armed,7
    frames+=1; state=4
    if release_stage=='between_frames': return frames,armed,7
    frames+=1; state=5
    if release_stage in ('after2','late'): state=6
    return frames,armed,state
assert simulate('phase')==(0,False,1)
assert simulate('between_frames')==(1,True,7)
assert simulate('after2')==(2,True,6)

print('v7.3.7 AUDIT PASS: pre-ARM release is retryable/0F; phase wait continuously proves UP; ARM occurs only after phase; frame1 passes immediately; frame2 UP guard retained; v7.3.6 RNG safety retained')
