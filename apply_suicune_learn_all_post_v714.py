#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')


def need(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f'v714 missing {label}: {marker}')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'v714 {label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)


def function_span(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f'v714 function not found: {signature}')
    brace = text.find('{', start)
    if brace < 0:
        raise SystemExit(f'v714 function brace not found: {signature}')
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit(f'v714 unclosed function: {signature}')


t = T.read_text()
for marker, label in [
    ('S713 SCAN', 'v7.1.3 UI epoch'),
    ('fn rebind_known_post_v713', 'v7.1.3 cross-branch resolver'),
    ('fn practical_wait_monitor', 'actual-root scanner'),
    ('practical_expected716_state', 'rel716 hard guard'),
    ('practical_expected717_state', 'rel717 hard guard'),
    ('STAGE3,V710', 'stage3 telemetry'),
    ('BRANCH710,V710', 'branch telemetry'),
]:
    need(t, marker, label)

# Generalize the existing Stage3 D/r15 donor-learning path.  A rel40 POST with
# an exact fingerprint (valid + score 0) is useful donor evidence even when it
# is not yet represented by a proven/empirical suffix model.  LEARN deliberately
# drops the shiny guarantee and keeps the probe alive so stop2/DV can be logged.
fs, fe = function_span(t, '    fn enter_stage3_learn(&mut self,p:u8,r:u8)')
learn_new = '''    fn enter_stage3_learn(&mut self,p:u8,r:u8){
        self.practical_learn=1;
        self.practical_active=false;
        self.practical_candidate_valid=false;
        self.practical_empirical=false;
        self.practical_miss=0;
        self.practical_post_proto=p;
        self.practical_post_rot=r;
        self.practical_terminal_advance=0;
    }'''
t = t[:fs] + learn_new + t[fe:]

# Empirical READY path: keep CrossBranch first.  If no known shiny suffix can
# rebind but the POST fingerprint is exact, continue as a donor-learning run.
old_emp = "if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return"
new_emp = "if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return"
t = replace_once(t, old_emp, new_emp, 'empirical unknown-POST learn fallback')

# Proven READY path: same rule.  CrossBranch remains the first choice; LEARN is
# only the fallback after known suffix re-evaluation failed or no donor exists.
old_proven = "if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40);return}self.practical_fail(1);return"
new_proven = "if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40);return}self.practical_fail(1);return"
t = replace_once(t, old_proven, new_proven, 'proven unknown-POST learn fallback')

# Epoch bump and explicit branch display.  Hex proto is intentional: it avoids
# adding any formatting/runtime dependency while still making A/B/C/D obvious
# (41/42/43/44) in screenshots.
t = t.replace('"S713 ', '"S714 ')
t = replace_once(
    t,
    'pnp::println!("S714 LEARN D15");',
    'pnp::println!("S714 LEARN P{:02X} R{}",self.practical_post_proto,self.practical_post_rot);',
    'generic LEARN overlay',
)

# Static safety checks: v7.1.4 must not loosen scan-time READY criteria or the
# rel716/717 guards.  It only changes the rel40 failure fallback into learning.
need(t, 'S714 SCAN', 'v7.1.4 SCAN')
need(t, 'S714 READY UP+B', 'v7.1.4 READY')
need(t, 'S714 LEARN P{:02X} R{}', 'v7.1.4 LEARN overlay')
need(t, 'fn rebind_known_post_v713', 'CrossBranch retained')
need(t, 'fn practical_wait_monitor', 'actual-root scan retained')
need(t, 'practical_expected716_state', 'rel716 guard retained')
need(t, 'practical_expected717_state', 'rel717 guard retained')
if 'S713 SCAN' in t:
    raise SystemExit('v714 stale S713 SCAN remains')
if "post.proto==b'D'&&post.rot40==15" in t:
    raise SystemExit('v714 D15-only learning guard remains')

T.write_text(t)
print('Applied Suicune v7.1.4 LearnAllPost: exact unknown rel40 POSTs continue to donor DV capture')
