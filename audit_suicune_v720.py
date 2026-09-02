#!/usr/bin/env python3
from pathlib import Path

H=Path('reader_core/src/crystal/hook.rs').read_text()
T=Path('reader_core/src/crystal/trace.rs').read_text()
M=Path('3gx/sources/main.c').read_text()
ALL='\n'.join([H,T,M])

required={
    'phase scan UI':'S720 PHASE SCAN',
    'A/r10 target UI':'S720 PROBE A/r10',
    'phase run UI':'S720 PHASE RUN',
    'branch timing CSV':'BRPHASE,V720',
    'A tick ring':'pub a_tick: [u64; PRE_VBLANK_RING_LEN]',
    'AA delta ring':'pub aa_delta: [u32; PRE_VBLANK_RING_LEN]',
    'AB delta ring':'pub ab_delta: [u32; PRE_VBLANK_RING_LEN]',
    'timing completion':'finish_pre_vblank_sample(host_tick)',
    'A/r10 exact gate':"if proto != b'A' || rot != 10",
    'diagnostic sentinel':'practical_live_found_lane = 250',
    'physical UP+B':'(just_pressed & KEY_B) && (held & KEY_DUP)',
    'Exact2F safety':'suicune_auto_resume_pending && !(held & KEY_DUP)',
}
for label,marker in required.items():
    if marker not in ALL:
        raise SystemExit(f'FAIL missing {label}: {marker}')

# The v7.2 hook timing extension must not introduce a second timing sample or
# any additional emulator-state/DIV access. gb_read_mem already owns one
# system_tick and one F604 read before VBlank bookkeeping.
a=H.find('fn push_pre_vblank_sample(')
b=H.find('pub fn v53_vblank_hits()',a)
span=H[a:b]
for bad in ['pnp::system_tick()', 'pnp::read::<', 'reader.div()', 'rng_state()']:
    if bad in span:
        raise SystemExit(f'FAIL PRE timing ring performs hot-path read: {bad}')

# Probe build must not manufacture a shiny READY from the phase scan.
a=T.find('    fn live_root_monitor')
b=T.find('    fn practical_fail',a)
monitor=T[a:b]
for bad in ['evaluate_exact(', 'evaluate_empirical(', 'bind_practical_prediction(', 'pre_has_observed_branch_conflict(']:
    if bad in monitor:
        raise SystemExit(f'FAIL phase monitor still runs production predictor: {bad}')
if 'pnp::request_pause();' not in monitor:
    raise SystemExit('FAIL phase monitor does not pause on target PRE')

# Keep cleanup guarantees from v7.1.8.
for bad in ['SEARCH_HORIZON','ROLL_REFRESH_INTERVAL','TRANSPORT,V670','rolling_refresh_targets','suicune_delay_','R > VC RESET']:
    if bad in ALL:
        raise SystemExit(f'FAIL stale legacy path returned: {bad}')

print('AUDIT PASS v7.2.0: A/r10 diagnostic actual-root scan; passive host timing ring; no new hot-path reads; production shiny evaluator bypassed')
