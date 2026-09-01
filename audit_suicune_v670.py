#!/usr/bin/env python3
from pathlib import Path

p = Path('reader_core/src/crystal/practical.rs').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()
m = Path('3gx/sources/main.c').read_text()


def need(cond, msg):
    if not cond:
        raise SystemExit('AUDIT FAIL: ' + msg)

# Keep the conservative search policy and input/branch safety from v6.6.x.
need('pub const SEARCH_HORIZON: u32 = 12000;' in p, '12k horizon changed unexpectedly')
need('pub const MIN_SEARCH_LEAD: u32 = 180;' in p, '180-advance release margin missing')
need('pub const MIN_SUPPORT_WEIGHT: u8 = 4;' in p, 'support gate changed')
need('S670 READY UP+B' in t, 'UP+B READY path missing')
need('S670 RETRY B40 R>RESET' in t, 'B40 conservative retry missing')
need('S670 RETRY B716 R>RESET' in t and 'S670 RETRY B717 R>RESET' in t, 'late guards missing')
need('host_request_release_resume' in m, 'release-gated WAIT resume missing')
need('lane_for_post' not in t and 'evaluate_post' not in t, 'unsafe POST-only rebind reintroduced')

# Full-index DIV transport model.
need('pub fn normal_inc_full(index: u32) -> u8' in p, 'full-index increment helper missing')
for site in ('0x0008', '0x0009', '0x0562', '0x0563', '0x22b5', '0x22b6'):
    need(site in p, f'special DIV site {site} missing')
need('av = av.wrapping_add(normal_inc_full(*ai));' in p, 'A future step not full-index')
need('sv = sv.wrapping_add(normal_inc_full(*si));' in p, 'S future step not full-index')
need('*ai = (*ai).wrapping_add(1) & 0x3fff;' in p, 'A tracker wrap missing')
need('*si = (*si).wrapping_add(1) & 0x3fff;' in p, 'S tracker wrap missing')
need('!= practical::normal_inc_full(candidate.wrapping_add(j as u32))' in t, 'full-index PRE calibration missing')
need('let ai_now = ai_validate' in t and '& 0x3fff;' in t, 'full-index ADIV re-anchor missing')
need('let mut si = (sub_div_tracker().index().unwrap_or(0) as u32) & 0x3fff;' in t, 'bounded SDIV tracker missing')

# The old simple helper deliberately remains for compatibility; actual
# normal_step must not use it anymore.
need('pub fn normal_inc(index: u32) -> u8' in p, 'legacy 16-phase helper unexpectedly removed')
step_start = p.index('pub fn normal_step')
step_end = p.index('\n}', step_start) + 2
step = p[step_start:step_end]
need('normal_inc_full' in step and 'normal_inc(*' not in step, 'normal_step still uses 16-only cadence')

# ERR4 diagnostics must separate target overshoot / PRE mismatch / actual-root
# re-evaluation failure and automatically preserve one lightweight CSV.
for marker in (
    'self.set_transport_diag(1, missed, reader, actual_lane);',
    'self.set_transport_diag(2, idx, reader, actual_lane);',
    'self.set_transport_diag(3, idx, reader, actual_lane);',
    'S670 E4 {} K{}',
    '1 => "PASS"',
    '2 => "PRE"',
    '3 => "EVAL"',
    'TRANSPORT,V670',
    'self.save_transport_diag();',
):
    need(marker in t, 'transport diagnostic marker missing: ' + marker)

# Successful exact-target revalidation must still use the actual live state and
# DIV, not precomputed root equality.
need('practical::evaluate(lane_id, reader.rng_state(), measured_div())' in t, 'actual-root target evaluation missing')
need('root_ok' not in t, 'old predicted-root equality gate reintroduced')

# Search still advances every projected step; lead filtering happens after the
# step so state stays synchronized.
needle = '''for step in 1..=practical::SEARCH_HORIZON {
            practical::normal_step(&mut st, &mut div, &mut ai, &mut si);
            if step < practical::MIN_SEARCH_LEAD { continue; }'''
need(needle in t, 'projection loop order changed')

# Sanity-check the six measured exception flips against the documented base
# cadence. This mirrors the Rust helper without relying on a target runtime.
base = [0x12,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13,0x12,0x12,0x13]
special = {0x0008,0x0009,0x0562,0x0563,0x22b5,0x22b6}
def full_inc(i):
    n = i & 0x3fff
    x = base[n & 15]
    if n in special:
        x = 0x13 if x == 0x12 else 0x12
    return x
expected = {
    0x0008:0x13, 0x0009:0x12,
    0x0562:0x13, 0x0563:0x12,
    0x22b5:0x13, 0x22b6:0x12,
}
for i, e in expected.items():
    need(full_inc(i) == e, f'exception self-test failed at {i:04X}')
need(full_inc(0x4008) == 0x13, '0x4000 wrap self-test failed')

print('AUDIT OK: Suicune Transport Stable v6.7.0')
print('  - future normal_step uses full 0x4000 DIV index')
print('  - six measured cadence exception sites are active')
print('  - ADIV PRE calibration is full-index anchored')
print('  - ERR4 is split into PASS/PRE/EVAL with lightweight CSV')
print('  - UP+B Exact2F and conservative branch guards preserved')
