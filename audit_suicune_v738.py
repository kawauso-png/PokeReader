#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(x,msg):
    if not x: raise SystemExit('v738 audit FAIL: '+msg)
start=p.index('pub fn evaluate_adaptive_bucket(')
seg=p[start:p.index('\n}',start)+2]
need('ai==0 || si==0 || !empirical_window_safe(ai,si)' in seg,'tracker guard lost')
need('if DEEP_A[i] == l.primary_a && DEEP_S[i] == l.primary_s { continue; }' in seg,'primary/global deep dedup missing')
need('deep_support=deep_support.saturating_add(DEEP_WEIGHT[i])' in seg,'weighted support lost')
need('d<=4' in seg and 'd<=8' in seg and 'd<=16' in seg,'distance gate lost')
need('}else{\n        false' in seg,'>16 auto-arm rejection lost')
rstart=p.index('pub fn adaptive_bucket_radius')
rseg=p[rstart:p.index('\n}',rstart)+2]
need('else { 16 }' in rseg and '128' not in rseg,'display/effective radius is not capped at 16')
need('S738 CONF SHINY SCAN' in t and 'S738 SHINY LOCK' in t,'v738 UI missing')
need('BUCKET738,V738' in t,'v738 CSV marker missing')
need('SUICUNE_ROOT_LOCK_MAX_STEPS 200000U' in m,'watchdog basis lost')
need('suicune_root_lock_steps = 0;' in m and 'suicune_root_lock_failed = false;' in m,'watchdog rollover lost')
need('suicune_wait_up_after_b = true;' in m,'B->UP TwoStageArm lost')
need('suicune_phase_slot = 1;' in m,'SLOT1 fixed path lost')
print('v7.3.8 audit PASS: tracker-safe, deduplicated weighted confidence, radius16, watchdog/TwoStage/SLOT1 retained')
