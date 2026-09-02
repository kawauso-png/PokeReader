#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/practical.rs').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()


def need(text, marker, label):
    if marker not in text:
        raise SystemExit('missing ' + label + ': ' + marker)


def forbid(text, marker, label):
    if marker in text:
        raise SystemExit('forbidden ' + label + ': ' + marker)


# The actual-root scanner remains the foundation.  v7.2 must not reintroduce
# long-horizon transport from an old root.
need(T, 'fn practical_wait_monitor', 'actual-root monitor')
need(T, 'if cur==self.practical_live_last_advance{return}', 'one evaluation per current root')
need(T, 'let state=reader.rng_state();let div=measured_div();', 'actual current state/div')
need(T, 'pnp::request_pause();return', 'current-root immediate pause')

# POST is now globally identified for validation; PRE is telemetry only.
need(P, 'pub fn empirical_post_count_global', 'global empirical POST count')
need(P, 'pub fn empirical_lane_for_post_unique_global', 'global unique empirical POST lookup')
need(P, 'pub fn post_evidence_counts', 'POST evidence telemetry helper')
need(T, 'fn rebind_known_post_v720', 'v720 global POST resolver')
start = T.index('fn rebind_known_post_v720')
end = T.index('fn enter_stage3_learn', start)
resolver = T[start:end]
need(resolver, 'empirical_lane_for_post_unique_global', 'global empirical resolver path')
need(resolver, 'lane_for_post_unique', 'proven POST resolver path')
forbid(resolver, 'empirical_lane_for_pre_post', 'same-PRE empirical gating in v720 resolver')
forbid(resolver, 'origin_pre', 'PRE-conditioned v720 resolver')

# Ambiguous/unseen high-confidence POST must be observed, never guessed.
need(T, 'if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)', 'generic POST LEARN fallback')
need(T, 'self.practical_expected716_state', 'rel716 hard guard')
need(T, 'self.practical_expected717_state', 'rel717 hard guard')

# Validation epoch and telemetry must be unmistakable.
need(T, 'POSTBEAM,V720', 'v720 POST telemetry')
need(T, 'S720 SCAN', 'v720 scan UI')
need(T, 'S720 TEST UP+B', 'validation-only target UI')
forbid(T, 'S713 ', 'stale v713 UI')
forbid(T, 'fn rebind_known_post_v713', 'stale v713 resolver')

# No probability model is allowed in this validation layer.  Promotion must be
# based on held-out coverage from analyze_suicune_postbeam_v720.py.
for marker in ('post_probability', 'branch_probability', 'success_probability'):
    forbid(P + T, marker, 'unvalidated probability model')

print('v7.2 AUDIT PASS: actual-root scan retained; POST identity globalized only when unique; ambiguous/unseen POST -> LEARN; hard guards retained; no probability model')
