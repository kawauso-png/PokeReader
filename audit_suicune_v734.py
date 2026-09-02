#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(c,msg):
    if not c: raise SystemExit('v734 audit FAIL: '+msg)

need('pub fn evaluate_empirical_post(' in p,'branch-resolved empirical evaluator missing')
need('emp_pre_post(proto,rot,post_proto,post_rot)?' in p,'evaluator is not post-conditioned')
need("b'A',10,b'C',8,state,div,ai,si" in t,'scanner is not A/r10 bucket76 C/r8 model')
need('if bucket != 76 { return; }' in t,'live bucket76 gate missing')
need('out |= 1u32 << 28;' in t and 'out |= bucket << 12;' in t,'packed bucket telemetry missing')
need("bucket == 76U" in m,'pause root lock does not require bucket76')
need('#define SUICUNE_ROOT_LOCK_MAX_STEPS 4608U' in m,'bucket traversal horizon missing')
need('suicune_phase_slot = 1;' in m,'SLOT1 fixed control missing')
need('S734 SHINY B76 SCAN' in t,'shiny scan UI missing')
need('S734 B76 SHINY LOCK' in t,'bucket lock UI missing')
need('PHASEBUCKET,V734,76,C,8,1' in t,'phasebucket CSV telemetry missing')
need('B ARM -> UP' in t,'v733 two-stage arm not preserved')
need('suicune_wait_up_after_b' in m,'v733 two-stage state not preserved')
print('v7.3.4 audit PASS: shiny-only A/r10 bucket76 -> C/r8 probe, SLOT1, bucket-locked two-stage arm')
