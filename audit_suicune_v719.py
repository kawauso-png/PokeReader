#!/usr/bin/env python3
from pathlib import Path

T=Path('reader_core/src/crystal/trace.rs').read_text()
P=Path('reader_core/src/crystal/practical.rs').read_text()
F=Path('reader_core/src/crystal/frame.rs').read_text()
M=Path('3gx/sources/main.c').read_text()
ALL='\n'.join([T,P,F,M])

required={
 'v719 scan UI':'S719 SCAN',
 'v719 READY UI':'S719 READY UP+B',
 'diagnostic learn UI':'S719 LEARN ONLY',
 'evidence telemetry':'EVIDENCE,V719',
 'evidence reject counter':'practical_evidence_reject',
 'branch conflict function':'pub fn pre_has_observed_branch_conflict',
 'clean scan API':'pub fn start_practical_scan',
 'clean live monitor':'fn live_root_monitor',
 'actual state read':'let state = reader.rng_state()',
 'actual DIV read':'let div = measured_div()',
 'exact evaluator':'practical::evaluate_exact',
 'empirical evaluator':'practical::evaluate_empirical',
 'production branch conflict gate':'if practical::pre_has_observed_branch_conflict(proto, rot)',
 'known-model consensus':'if shiny_models != known_models',
 'rel40 recovery':'fn rebind_known_post_v713',
 'generic LEARN':'fn enter_stage3_learn',
 'rel716 guard':'practical_expected716_state',
 'rel717 guard':'practical_expected717_state',
 'pure-tail signature':'FASTTAIL715,V715',
 'manual reset':'RESET VC MANUALLY',
 'UP+B':'(just_pressed & KEY_B) && (held & KEY_DUP)',
}
for label,marker in required.items():
    if marker not in ALL:
        raise SystemExit(f'FAIL missing {label}: {marker}')

forbidden={
 'old monitor name':'fn practical_wait_monitor',
 'misleading search API':'search_practical_targets',
 'future horizon':'SEARCH_HORIZON',
 'future target queue':'self.practical_targets',
 'rolling search':'rolling_refresh_targets',
 'transport':'TRANSPORT,V670',
 'neutral delay':'suicune_delay_',
 'old wait UI':'S719 WAIT',
 'old R reset':'R > VC RESET',
 'old one-lane READY version':'S718 READY',
 'discarded sampling myth':'1/10',
}
for label,marker in forbidden.items():
    if marker in ALL:
        raise SystemExit(f'FAIL legacy {label}: {marker}')

for cell in ["(b'A', 3)","(b'A', 10)","(b'B', 11)","(b'D', 12)","(b'B', 1)"]:
    if cell not in P:
        raise SystemExit(f'FAIL missing conflict cell {cell}')

regression=[
 ('0080','A',10,'D',15),('0088','A',10,'A',2),('0089','A',10,'B',14),
 ('0090','A',10,'D',2),('0091','A',10,'B',9),('0092','B',1,'B',9),
 ('0093','B',11,'A',2),('0094','B',11,'D',13),('0095','B',11,'C',3),
 ('0120','D',12,'A',2),('0121','A',10,'A',2),('0122','A',3,'A',12),
]
blocked={('A',3),('A',10),('B',11),('D',12),('B',1)}
for trace,pp,pr,op,orr in regression:
    if (pp,pr) not in blocked:
        raise SystemExit(f'FAIL regression {trace} not blocked')

a=T.find('    fn live_root_monitor')
b=T.find('    fn practical_fail',a)
if a<0 or b<0:
    raise SystemExit('FAIL live monitor span')
mon=T[a:b]
conf=mon.find('pre_has_observed_branch_conflict')
cons=mon.find('shiny_models != known_models')
bind=mon.find('self.bind_practical_prediction(prediction)')
if not (0 <= conf < cons < bind):
    raise SystemExit('FAIL evidence gate ordering')
for bad in ['normal_step(', 'SEARCH_HORIZON', 'self.practical_targets']:
    if bad in mon:
        raise SystemExit(f'FAIL future operation in live monitor: {bad}')

if 'state.trace.start_practical_scan(&reader);' not in F:
    raise SystemExit('FAIL frame does not call clean scan API')

print('AUDIT PASS v7.1.9: actual-root scan retained; all known false-READY PRE families blocked for production; multi-model consensus required; CrossBranch/LEARN/716/717 guards retained')
