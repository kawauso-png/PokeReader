#!/usr/bin/env python3
from pathlib import Path
import re

P = Path('reader_core/src/crystal/practical.rs').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()


def need(text, marker, label):
    if marker not in text:
        raise SystemExit('v721 missing ' + label + ': ' + marker)


def forbid(text, marker, label):
    if marker in text:
        raise SystemExit('v721 forbidden ' + label + ': ' + marker)


# Architecture inherited from v7.2 must remain intact.
for marker, label in [
    ('fn practical_wait_monitor', 'actual-root scanner'),
    ('let state=reader.rng_state();let div=measured_div();', 'actual current root'),
    ('pnp::request_pause();return', 'immediate candidate pause'),
    ('fn rebind_known_post_v720', 'POSTBEAM rel40 resolver'),
    ('empirical_lane_for_post_unique_global', 'global unique POST lookup'),
    ('practical_expected716_state', 'rel716 hard guard'),
    ('practical_expected717_state', 'rel717 hard guard'),
    ('POSTBEAM,V720', 'v720 telemetry compatibility'),
]:
    need(T if marker.startswith('fn practical') or marker.startswith('let state') or marker.startswith('pnp::') or marker.startswith('fn rebind') or marker.startswith('practical_') or marker.startswith('POSTBEAM') else P, marker, label)

# PRE-C coverage: source0103 is the only newly admitted target-side lane.
need(P, 'const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=6;', 'six-lane empirical bank')
need(P, "EmpLane{id:106,source:103,pre_proto:b'C',pre_rot:7,post_proto:b'B',post_rot:6,route:4", '0103 C/r7 lane')
need(P, 'full_a:&E6_FA,full_s:&E6_FS', '0103 full suffix tables')
need(P, 'last_a:2,last_s:2', '0103 rel730 terminal base offset')

# The route4 fix must be lane-specific.  A global replacement would break 0101.
need(P, 'const EMP_R4_A:[u8;4]=[183,185,191,193];', 'old 0101 route4 tail')
need(P, 'const EMP_R4_ALT_A:[u8;4]=[184,186,192,194];', 'held-out route4 tail')
need(P, 'if source==103{(EMP_R4_ALT_A[j],EMP_R4_ALT_S[j])}else{(EMP_R4_A[j],EMP_R4_S[j])}', 'source-specific route4 selector')
if P.count('emp_r4_step(l.source,j)') != 2:
    raise SystemExit('v721 route4 selector must be used by target and rel40 evaluators exactly twice')

# No weakening of PRE classification or cadence safety in this fix.
need(T, 'if !ok||best!=0{return None}', 'exact PRE fingerprint requirement')
need(P, 'pub fn empirical_window_safe', 'cadence exception guard')
forbid(T, 'best<=', 'relaxed PRE score threshold')

# The overlay must make future coverage failures observable.
need(T, 'S721 SCAN', 'v721 scan epoch')
need(T, 'S721 TEST UP+B', 'validation-only candidate UI')
need(T, 'FP {}{} K{}', 'live PRE/known-cell diagnostic')
forbid(T, 'S720 ', 'stale v720 UI')

# A tiny independent algebra regression, duplicated here so a later edit cannot
# silently remove the evidence gates in the patch script.
def upd(st, a, s):
    h, l = (st >> 8) & 255, st & 255
    z = h + a
    c = 1 if z > 255 else 0
    return ((z & 255) << 8) | ((l - s - c) & 255)


def raw4(st, ba, bs, aa, ss):
    q = []
    for a, s in zip(aa, ss):
        st = upd(st, (ba + a) & 255, (bs + s) & 255)
        q.append(st & 255)
    return q

old_a = [183,185,191,193]
old_s = [183,186,191,193]
alt = [184,186,192,194]
q101 = raw4(0xADB8, 0x04, 0x04, old_a, old_s)
q102 = raw4(0x7C64, 0xBC, 0xBC, alt, alt)
q103 = raw4(0xDC41, 0xC5, 0xC5, alt, alt)
assert q101[0] >= 0xC0 and ((q101[2] << 8) | q101[3]) == 0x7AB4
assert q102[0] >= 0xC0 and ((q102[2] << 8) | q102[3]) == 0xFD7E
assert q103[0] >= 0xC0 and ((q103[2] << 8) | q103[3]) == 0xBE37

print('v7.2.1 AUDIT PASS: actual-root/POSTBEAM unchanged; PRE C/r7 added; route4 tail is lane-specific; 0101 + held-out 0102/0103 algebra regressions pass; PRE score remains exact')
