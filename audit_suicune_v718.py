#!/usr/bin/env python3
from pathlib import Path

T=Path('reader_core/src/crystal/trace.rs').read_text()
P=Path('reader_core/src/crystal/practical.rs').read_text()
I=Path('reader_core/src/pnp/input.rs').read_text()
B=Path('reader_core/src/pnp/bindings.rs').read_text()
M=Path('3gx/sources/main.c').read_text()
ALL='\n'.join([T,P,I,B,M])

required = {
    'current scan UI':'S718 SCAN',
    'current READY UI':'S718 READY UP+B',
    'manual reset truth':'RESET VC MANUALLY',
    'current telemetry':'PRACTICAL,V718',
    'live actual-root monitor':'fn practical_wait_monitor',
    'actual state read':'let state=reader.rng_state()',
    'actual measured DIV':'let div=measured_div()',
    'exact evaluator':'practical::evaluate_exact',
    'empirical evaluator':'practical::evaluate_empirical',
    'CrossBranch':'fn rebind_known_post_v713',
    'generic learn':'fn enter_stage3_learn',
    'rel716 guard':'practical_expected716_state',
    'rel717 guard':'practical_expected717_state',
    'pure tail fingerprint':'FASTTAIL715,V715',
    'fresh scan reset':'fn reset_scan_epoch',
    'UP+B host trigger':'(just_pressed & KEY_B) && (held & KEY_DUP)',
    'release gated fixed run':'if (fixed_run_pending)',
    'exact UP safety':'suicune_auto_resume_pending && !(held & KEY_DUP)',
    'timing compatibility quarantine':'old Early Control/parity hypothesis is rejected',
}
for label, marker in required.items():
    if marker not in ALL:
        raise SystemExit(f'FAIL missing {label}: {marker}')

forbidden = {
    'future horizon':'SEARCH_HORIZON',
    'future lead':'MIN_SEARCH_LEAD',
    'rolling interval':'ROLL_REFRESH_INTERVAL',
    'rolling lock':'ROLL_LOCK_LEAD',
    'candidate queue size':'MAX_SEARCH_CANDIDATES',
    'future normal stepping':'pub fn normal_step(',
    'rolling future function':'rolling_refresh_targets',
    'transport telemetry':'TRANSPORT,V670',
    'rolling telemetry':'ROLL,V671',
    'old WAIT UI':'S718 WAIT',
    'dead transport fields':'practical_transport_',
    'dead rolling fields':'practical_roll_',
    'dead queue arrays':'practical_targets',
    'neutral delay runtime':'suicune_delay_',
    'old Y+X Suicune handler':'// Y + X arms Suicune Deep Probe',
    'wrong R-reset instruction':'R > VC RESET',
    'discarded sampling myth':'1/10',
}
for label, marker in forbidden.items():
    if marker in ALL:
        raise SystemExit(f'FAIL legacy {label} remains: {marker}')

# The current root monitor itself must not project/step into future state.
a=T.find('    fn practical_wait_monitor')
b=T.find('    fn practical_fail',a)
if a < 0 or b < 0:
    raise SystemExit('FAIL monitor span')
monitor=T[a:b]
for bad in ['normal_step(', 'SEARCH_HORIZON', 'practical_targets', 'wrapping_add(step)']:
    if bad in monitor:
        raise SystemExit(f'FAIL monitor contains future-search operation: {bad}')

# Generic trace controls may remain, but the Suicune execution route must have
# only one arm trigger: the current physical UP+B path.
if M.count('arm_suicune_probe();') != 1:
    raise SystemExit(f'FAIL expected one Suicune arm path, got {M.count("arm_suicune_probe();")}')

print('AUDIT PASS v7.1.8: actual-root Stage3 retained; dead future transport/neutral-delay/Y+X removed; reset wording corrected; timing-compat observation quarantined')
