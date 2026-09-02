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
    'separate timing ring':'pub struct PreVBlankTimingRing',
    'A tick ring':'pub a_tick: [u64; PRE_VBLANK_RING_LEN]',
    'B tick ring':'pub b_tick: [u64; PRE_VBLANK_RING_LEN]',
    'timing start':'pre_vblank_timing_capture_start()',
    'timing stop':'pre_vblank_timing_capture_stop()',
    'timing snapshot':'latest_pre_vblank_timing_ring()',
    'B completion':'finish_pre_vblank_timing_sample(host_tick)',
    '17-root warmup':'self.practical_live_checked < PRE_VBLANK_RING_LEN as u32',
    'A/r10 exact gate':"if proto != b'A' || rot != 10",
    'diagnostic sentinel':'practical_live_found_lane = 250',
    'physical UP+B':'(just_pressed & KEY_B) && (held & KEY_DUP)',
    'Exact2F safety':'suicune_auto_resume_pending && !(held & KEY_DUP)',
}
for label,marker in required.items():
    if marker not in ALL:
        raise SystemExit(f'FAIL missing {label}: {marker}')

# Production classifier ring must remain slim. live_pre_cell() copies this
# structure by value on each actionable root, so host timing must not live here.
a=H.find('pub struct PreVBlankRing {')
b=H.find('impl PreVBlankRing',a)
if a<0 or b<0:
    raise SystemExit('FAIL PreVBlankRing span')
pre=H[a:b]
for bad in ['a_tick','b_tick','aa_delta','ab_delta','u64']:
    if bad in pre:
        raise SystemExit(f'FAIL production PRE ring enlarged by timing field: {bad}')

# The hot rDIV extension may only use the host_tick argument already sampled by
# gb_read_mem. No second timer sample, DIV/RNG read, emulator-memory read, or
# delta arithmetic is allowed in the timing helper span.
a=H.find('pub struct PreVBlankTimingRing')
b=H.find('pub fn v53_vblank_hits()',a)
if a<0 or b<0:
    raise SystemExit('FAIL timing helper span')
span=H[a:b]
for bad in ['pnp::system_tick()', 'pnp::read::<', 'reader.div()', 'rng_state()', 'saturating_sub(']:
    if bad in span:
        raise SystemExit(f'FAIL timing ring performs extra hot-path work: {bad}')

# Full timing-ring copies are allowed only at UP+B arm/save, never in live PRE
# classification or live-root scanning.
a=T.find('    fn live_pre_cell')
b=T.find('    fn bind_practical_prediction',a)
livepre=T[a:b]
if 'latest_pre_vblank_timing_ring' in livepre:
    raise SystemExit('FAIL live_pre_cell copies timing ring')
a=T.find('    fn live_root_monitor')
b=T.find('    fn practical_fail',a)
monitor=T[a:b]
if 'latest_pre_vblank_timing_ring' in monitor:
    raise SystemExit('FAIL live_root_monitor copies timing ring')
for bad in ['evaluate_exact(', 'evaluate_empirical(', 'bind_practical_prediction(', 'pre_has_observed_branch_conflict(']:
    if bad in monitor:
        raise SystemExit(f'FAIL phase monitor still runs production predictor: {bad}')
if 'pnp::request_pause();' not in monitor or 'pre_vblank_timing_capture_stop();' not in monitor:
    raise SystemExit('FAIL phase target does not stop capture and pause')

# Timing snapshot must occur once in the frozen UP+B arm path.
a=T.find('    pub fn arm_suicune_probe')
b=T.find('    pub fn',a+10)
arm=T[a:b]
if arm.count('latest_pre_vblank_timing_ring()') != 1:
    raise SystemExit('FAIL timing ring is not snapped exactly once at arm')

# Keep cleanup guarantees from v7.1.8.
for bad in ['SEARCH_HORIZON','ROLL_REFRESH_INTERVAL','TRANSPORT,V670','rolling_refresh_targets','suicune_delay_','R > VC RESET']:
    if bad in ALL:
        raise SystemExit(f'FAIL stale legacy path returned: {bad}')

print('AUDIT PASS v7.2.0: slim production PRE ring; separate gated A/B host-tick ring; no extra hot-path reads/delta math; A/r10 diagnostic scan only')
