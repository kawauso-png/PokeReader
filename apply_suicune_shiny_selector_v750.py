#!/usr/bin/env python3
from pathlib import Path
import re

M = Path('3gx/sources/main.c')
T = Path('reader_core/src/crystal/trace.rs')
P = Path('reader_core/src/crystal/practical.rs')

m = M.read_text()
t = T.read_text()
p = P.read_text()

# -------------------------------------------------------------------------
# Suicune v7.5.0 Shiny Selector / VC Reset Retry
#
# Production boundary:
#   * read-only RNG / DIV / phase observation
#   * current-root / future-candidate search is allowed
#   * Exact-2F and PokeReader Pause are allowed as input-timing assistance
#   * NO RNG/DIV/DV writes
#   * NO host-tick waiting to choose START/Resume phase
#   * a failed live gate returns to a VC-reset retry, never donor LEARN
# -------------------------------------------------------------------------

# v7.3.8 contains three tight host-tick waits inherited from START/Resume/
# cadence causal experiments. Keep their telemetry but remove their causal
# effect. Failing closed if the count changes prevents accidental phase
# manipulation in a future production build.
wait_pat = re.compile(r'\s*while\s*\(\s*svcGetSystemTick\(\)\s*<\s*target\s*\)\s*\{\s*\}')
waits = list(wait_pat.finditer(m))
if len(waits) != 3:
    raise SystemExit(f'v750 expected exactly 3 inherited host-phase waits, found {len(waits)}')
m = wait_pat.sub('\n                    /* v7.5 natural phase: telemetry target only; do not wait */', m)
if re.search(r'while\s*\(\s*svcGetSystemTick\(\)\s*<', m):
    raise SystemExit('v750 found an unexpected remaining host-tick wait')

# Production identity.
t = t.replace('S738 A-EPOCH SCAN', 'S750 SHINY SCAN')
t = t.replace('S738 CONF SHINY SCAN', 'S750 SHINY SCAN')
t = t.replace('S738 SHINY LOCK', 'S750 SHINY READY')
t = t.replace('BUCKET738,V738,', 'BUCKET750,V750,')
t = t.replace('S732 NEED A EPOCH', 'S750 NEED A EPOCH')
t = t.replace('S719 RESET RECOMMENDED', 'S750 VC RESET')
t = t.replace('RESET VC MANUALLY', 'R -> VC RESET')
m = m.replace('S738', 'S750')

# Stale causal-control labels are telemetry-only in v7.5.
for old in (
    'ABS SLOT{} FIXED',
    'ABS SLOT{} X=TOGGLE',
    'SLOT0 BASE  X=+1',
):
    t = t.replace(old, 'NATURAL RESUME')

# -------------------------------------------------------------------------
# Result-gate policy.
# v7.3.8 is an analysis build and intentionally enters Stage3 LEARN when a
# candidate's observed POST/B716/B717 leaves the predicted path. For an actual
# shiny attempt that is the wrong behavior: the selected shiny hypothesis has
# failed, so stop before wasting the rest of the encounter and retry via VC
# Reset. Known-post rebind remains allowed in the legacy empirical paths; if a
# rebind succeeds it is still a real observed path and can safely continue.
# -------------------------------------------------------------------------

# Bucket-model rel40: any mismatch invalidates this selected candidate.
old = 'if !ok{if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}'
new = 'if !ok{self.practical_fail(1);return}'
if t.count(old) != 1:
    raise SystemExit(f'v750 bucket B40 learn block count {t.count(old)}')
t = t.replace(old, new, 1)

# Bucket-model B716/B717: reset instead of entering donor learning.
old716 = 'if e.state!=self.practical_expected716_state||e.div!=self.practical_expected716_div{self.enter_stage3_learn(self.practical_post_proto,self.practical_post_rot);return}'
old717 = 'if e.state!=self.practical_expected717_state||e.div!=self.practical_expected717_div{self.enter_stage3_learn(self.practical_post_proto,self.practical_post_rot);return}'
if t.count(old716) != 1 or t.count(old717) != 1:
    raise SystemExit(f'v750 bucket late learn blocks counts {t.count(old716)}/{t.count(old717)}')
t = t.replace(old716, 'if e.state!=self.practical_expected716_state||e.div!=self.practical_expected716_div{self.practical_fail(2);return}', 1)
t = t.replace(old717, 'if e.state!=self.practical_expected717_state||e.div!=self.practical_expected717_div{self.practical_fail(3);return}', 1)

# Empirical and legacy exact paths may first salvage a mismatch by rebinding to
# an actually observed known POST. If rebind fails, reset; never switch to LEARN.
old = 'if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return'
if t.count(old) != 1:
    raise SystemExit(f'v750 empirical B40 learn block count {t.count(old)}')
t = t.replace(old, 'self.practical_fail(1);return', 1)
old = 'if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40);return}self.practical_fail(1);return'
if t.count(old) != 1:
    raise SystemExit(f'v750 exact B40 learn block count {t.count(old)}')
t = t.replace(old, 'self.practical_fail(1);return', 1)

marker = 'BUCKET750,V750,'
if marker not in t:
    raise SystemExit('v750 bucket CSV version marker missing')

required = [
    'pub fn evaluate_adaptive_bucket(',
    'primary_shiny',
    'deep_support',
    'practical_expected40_state',
    'practical_expected716_state',
    'practical_expected717_state',
    'fn practical_fail',
    'host_request_resume',
    'S750 SHINY READY',
    'S750 VC RESET',
]
blob = p + '\n' + t + '\n' + m
missing = [x for x in required if x not in blob]
if missing:
    raise SystemExit(f'v750 required production markers missing: {missing}')

# No analysis-only LEARN transition may remain inside the active practical gate.
gate_a = t.find('if self.practical_active{')
gate_b = t.find('if self.probe_active && window[2] == SUICUNE_SPECIES', gate_a)
if gate_a < 0 or gate_b < 0:
    raise SystemExit('v750 could not isolate practical result gate')
if 'enter_stage3_learn' in t[gate_a:gate_b]:
    raise SystemExit('v750 practical result gate still contains LEARN transition')

# Narrow policy guard for the Japanese DV watch bytes.
for forbidden in (
    'write_u16(0xd23d',
    'write_u8(0xd23d',
    'write_u16(0xd23e',
    'write_u8(0xd23e',
):
    if forbidden in blob.lower():
        raise SystemExit(f'v750 forbidden DV write marker present: {forbidden}')

M.write_text(m)
T.write_text(t)
P.write_text(p)
print('Applied Suicune v7.5.0 Shiny Selector: natural phase + reset-only live gates + VC retry')
