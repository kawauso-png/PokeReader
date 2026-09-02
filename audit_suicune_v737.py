#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(x,msg):
    if not x: raise SystemExit('v737 audit FAIL: '+msg)
need('evaluate_adaptive_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32,steps:u32)' in p,'AI/SI evaluator signature missing')
need('ai==0 || si==0 || !empirical_window_safe(ai,si)' in p,'tracker safety guard missing')
need('deep_support=deep_support.saturating_add(DEEP_WEIGHT[i])' in p,'weighted deep support missing')
need('primary_shiny || deep_support>=4' in p,'near-anchor confidence gate missing')
need('d<=8' in p and 'deep_support>=6' in p,'medium confidence gate missing')
need('d<=16' in p and 'deep_support>=8' in p,'distance16 confidence gate missing')
segment=p[p.index('let accept='):p.index('if !accept')]
need('else{\n        false' in segment or 'else{\r\n        false' in segment,'far extrapolation rejection missing')
need('DEEP_WEIGHT[i]' in segment or 'DEEP_WEIGHT[i]' in p,'historical weights not used')
need('practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_div_tracker().index().unwrap_or(0) as u32,sub_div_tracker().index().unwrap_or(0) as u32,self.bucket_scan_steps)' in t,'trace call does not pass tracker indices')
need('BUCKET737,V737' in t,'v737 CSV marker missing')
need('S737 CONF SHINY SCAN' in t and 'S737 SHINY LOCK' in t,'v737 UI missing')
need('SUICUNE_ROOT_LOCK_MAX_STEPS 200000U' in m,'v736 watchdog basis lost')
need('suicune_root_lock_steps = 0;' in m and 'suicune_root_lock_failed = false;' in m,'watchdog rollover lost')
need('suicune_wait_up_after_b = true;' in m,'TwoStageArm lost')
need('suicune_phase_slot = 1;' in m,'SLOT1 fixed path lost')
print('v7.3.7 audit PASS: tracker-safe, weighted confidence gate, >16 extrapolation blocked, watchdog/TwoStage/SLOT1 retained')
