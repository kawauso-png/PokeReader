#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(c,msg):
    if not c: raise SystemExit('v736 audit FAIL: '+msg)

need('if steps < 2048 { 4 }' in p,'radius4 threshold')
need('else if steps < 6144 { 8 }' in p,'radius8 threshold')
need('else if steps < 12288 { 16 }' in p,'radius16 threshold')
need('else { 128 }' in p,'full-range threshold')
need('suicune_root_lock_steps = 0;' in m,'watchdog rollover reset')
blk=m[m.find('if (suicune_root_lock_steps >= SUICUNE_ROOT_LOCK_MAX_STEPS)'):m.find('const u32 lock_block_keys',m.find('if (suicune_root_lock_steps >= SUICUNE_ROOT_LOCK_MAX_STEPS)'))]
need('suicune_root_lock_failed = true' not in blk,'watchdog still fails search')
need('suicune_root_lock_active = false' not in blk,'watchdog still deactivates search')
need('S736 PAUSE SHINY SCAN' in t,'v736 scan UI')
need('S736 SHINY LOCK' in t,'v736 lock UI')
need('BUCKET736,V736' in t,'v736 CSV tag')
need('evaluate_adaptive_bucket' in p and 'source:132,anchor:39' in p and 'source:128,anchor:76' in p and 'source:130,anchor:94' in p and 'source:129,anchor:112' in p and 'source:131,anchor:207' in p,'v735 donor model lost')
need('suicune_wait_up_after_b = true;' in m,'two-stage arm lost')
print('v7.3.6 audit PASS: full range at N12288; watchdog rolls over without silent stall; v735 model/TwoStageArm retained')
