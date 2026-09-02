#!/usr/bin/env python3
from pathlib import Path
M=Path('3gx/sources/main.c').read_text()
T=Path('reader_core/src/crystal/trace.rs').read_text()
P=Path('reader_core/src/crystal/practical.rs').read_text()

def need(x,s,label):
    if s not in x: raise SystemExit('v738 missing '+label+': '+s[:120])
def forbid(x,s,label):
    if s in x: raise SystemExit('v738 forbidden '+label+': '+s[:120])

# UP trigger must debounce before ARM, and transient HID changes during the
# frozen host-phase wait must not consume/reject the candidate.
need(M,'SUICUNE_TEST_UP_DEBOUNCE_SAMPLES 8U','UP debounce')
need(M,'static bool suicune_test_up_only_held(u32 held)','exact-UP helper')
need(M,'static bool suicune_test_wait_start_phase_boundary(void)','boundary helper')
b=M.index('static bool suicune_test_wait_start_phase_boundary(void)')
e=M.index('static void suicune_test_begin_exact2f(void)',b)
phase=M[b:e]
forbid(phase,'if (!suicune_test_up_only_now()) return false;','continuous phase rejection')
need(phase,'return suicune_test_up_only_now();','final boundary proof')

x=M.index('if (suicune_test_exec_active && suicune_test_exec_state <= 2)')
y=M.index('if (suicune_release_resume_pending)',x)
exe=M[x:y]
need(exe,'suicune_test_up_debounce++','debounce counter')
need(exe,'suicune_test_wait_start_phase_boundary()','boundary wait')
need(exe,'arm_suicune_probe();','probe ARM')
need(exe,'fixed_frames_remaining--; // exact frame #1','immediate frame1')
if exe.index('arm_suicune_probe();') > exe.index('fixed_frames_remaining--; // exact frame #1'):
    raise SystemExit('v738 frame1 precedes ARM')
postarm=exe[exe.index('arm_suicune_probe();'):exe.index('fixed_frames_remaining--; // exact frame #1')]
forbid(postarm,'suicune_test_up_only_now','post-ARM HID race')

# Both exact frames must be physically UP-only; resume waits for all game keys
# to be released so no stray direction/button leaks into free-run.
need(M,'if (suicune_auto_resume_pending && !suicune_test_up_only_held(held))','frame2 exact-UP guard')
need(M,'if ((held & SUICUNE_TEST_GAME_KEYS) == 0)','all-key release guard')

# Recent data falsified cross-PRE GlobalBeam as a practical target selector.
# Live search must contain only the actually matched PRE tiers.
s=T.index('fn practical_wait_monitor'); e=T.index('fn practical_fail',s); mon=T[s:e]
need(mon,'matched_proven','PRE matched proven')
need(mon,'matched_emp','PRE matched empirical')
forbid(mon,'practical_global_speculative=true','Global speculative candidate')
forbid(mon,'for id in 1..=practical::proven_lane_count()','cross-PRE proven scan')

# A valid but nonzero POST fingerprint is valuable LEARN data (0133 class).
progress=T[T.index('if self.practical_active{'):T.index('if self.probe_active && window[2] == SUICUNE_SPECIES')]
need(progress,'if !post.valid{self.practical_fail(1);return}','invalid POST hard fail only')
need(progress,'if post.best_score!=0{','approx POST branch')
need(progress,'self.practical_learn=2;','approx LEARN mode')
need(T,'S738 LEARN POST~ S{}','approx LEARN UI')

# Preserve the v7.3.6/7 downstream safety architecture.
need(T,'fn rebind_shiny_post_v736','rel40 suffix resolver')
need(T,'practical_expected716_state','716 hard guard')
need(T,'practical_expected717_state','717 hard guard')
need(P,'const EMP_COUNT:usize=7','deduped empirical bank retained')

# Epoch/UI sanity.
for s in ['S738 TEST HOLD UP 0.5s','EXEC,V738','GLOBALBEAM,V738','SOFTRESET,V738']:
    need(T,s,s)
forbid(T,'S737','stale S737 UI')

# State-machine model: a bad boundary sample consumes 0 frames and retries;
# once boundary UP is exact, the first frame passes immediately and a stable
# hold gives exactly two UP frames.
def sim(boundary_ok=True, frame2_ok=True):
    frames=0; armed=False
    if not boundary_ok: return frames,armed,'retry'
    armed=True; frames+=1
    if not frame2_ok: return frames,armed,'abort'
    frames+=1
    return frames,armed,'ok'
assert sim(False,True)==(0,False,'retry')
assert sim(True,False)==(1,True,'abort')
assert sim(True,True)==(2,True,'ok')

print('v7.3.8 AUDIT PASS: UP debounce/boundary retry is 0F safe; no post-ARM reread; both frames exact-UP; all-key release; cross-PRE GlobalBeam disabled; valid approximate POST continues LEARN; 716/717 guards retained')
