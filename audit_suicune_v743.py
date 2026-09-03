#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs').read_text(); t=Path('reader_core/src/crystal/trace.rs').read_text(); m=Path('3gx/sources/main.c').read_text()
def need(x,msg):
    if not x: raise SystemExit('v743 audit FAIL: '+msg)
need('pub fn evaluate_m14_b9_dual' in p,'M14 dual evaluator missing')
need('let l=lane(3);' in p and 'source:95' in p,'historical B/r9 donor source95 missing')
need('EMP_R4_A' in p and 'r4valid' in p,'route4 evaluator missing')
need('r3support>=MIN_SUPPORT_WEIGHT' in p,'route3 weighted support gate missing')
need('bucket!=76' in t,'B76-only live gate missing')
need('evaluate_m14_b9_dual(reader.rng_state(),measured_div(),ai,si)' in t,'live M14 evaluator call missing')
need('S743 M14 TURBO' in t and 'S743 M14 SHINY LOCK' in t,'v743 UI missing')
need('B76 A/r10 START M0 RES M14' in t,'fixed actuator UI missing')
need('suicune_phase_slot = 14U;' in m,'fixed M14 resume missing')
need('while (((u32)cycle & 15U) != wanted) cycle++;' in m,'full16 absolute resume actuator lost')
need('wanted_start_cycle = 0U' in m,'absolute START M0 lost')
need('suicune_wait_up_after_b = true;' in m,'TwoStageArm lost')
need('just_pressed & KEY_DUP' not in m[m.index('// Stage3 current-root live scan start.'):m.index('// Y + right / Y + left adjusts',m.index('// Stage3 current-root live scan start.'))],'B39 alternate scan still exposed')
print('v7.4.3 audit PASS: B76 Turbo, dual B/r9 route3/route4 shiny gate, START M0, Resume M14, TwoStageArm retained')
