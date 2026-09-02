#!/usr/bin/env python3
from pathlib import Path

m = Path('3gx/sources/main.c').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()

checks = []
def need(cond, msg):
    checks.append((cond, msg))

need('S730 A10 CONTROL' in t, 'scan UI missing')
need('S730 NEED A EPOCH' in t, 'non-A fast reset UI missing')
need('S730 A/r10 READY' in t, 'A/r10 ready UI missing')
need('ABS SLOT{} X=TOGGLE' in t, 'slot selector UI missing')
need("if proto0 != b'A'" in t, 'non-A epoch rejection missing')
need('if rot != 10 { return; }' in t, 'A/r10 selector missing')
need('self.practical_live_found_lane = 254' in t, 'NEED-A sentinel missing')
need('self.practical_live_found_lane = 253' in t, 'control probe sentinel missing')
need('self.practical_live_checked>=3000' not in t and 'self.practical_live_checked >= 3000' not in t, '3000FR fallback survived')
need('FALLBACK ANY EXACT' not in t, 'fallback UI survived')
need('PHASESCAN,V730' in t and 'PRECOUNT,V730' in t, 'v730 scan CSV version missing')
need('CONTROL,V730,A,10' in t, 'control CSV row missing')

need('static u32 suicune_phase_slot = 1;' in m, 'default absolute slot1 missing')
need('(suicune_phase_slot == 1) ? 6 : 1' in m, 'X slot1/6 toggle missing')
need('u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;' in m, 'absolute cycle calculation missing')
need('((u32)cycle & 7U) != wanted' in m, 'absolute mod8 targeting missing')
need('u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;' in m, 'absolute boundary target missing')
need('SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_phase_slot' not in m, 'old relative slot-offset wait survived')
need('suicune_phase_anchor_tick + offset' not in m, 'old anchor-relative target survived')
need('(held & KEY_B) && (held & KEY_DUP)' in m, 'robust UP+B held latch missing')
need('(KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)' in m, 'B release gate missing')
need('(KEY_DUP | KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)' in m, 'post-2F release mask missing')
need('suicune_auto_resume_pending && !(held & KEY_DUP)' in m, 'physical UP release safety missing')

# The control scanner must stay diagnostic: no production shiny evaluator may
# decide whether the current root is accepted.
a = t.find('    fn live_root_monitor(&mut self, reader: &Gen2Reader)')
b = t.find('\n    fn ', a + 10)
span = t[a:b if b > a else len(t)]
for forbidden in ('evaluate_exact(', 'evaluate_empirical(', 'bind_practical_prediction(', 'practical_conflicted_pre('):
    need(forbidden not in span, f'production decision leaked into v730 monitor: {forbidden}')
need('pnp::request_pause();' in span, 'control monitor never pauses')
need('add_div_tracker().index()' not in span and 'sub_div_tracker().index()' not in span, 'index gate leaked back into control monitor')

bad = [msg for ok, msg in checks if not ok]
if bad:
    for msg in bad:
        print('FAIL:', msg)
    raise SystemExit(1)
print(f'v7.3.0 audit PASS ({len(checks)} checks)')
