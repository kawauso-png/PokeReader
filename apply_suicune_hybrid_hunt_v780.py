from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v780 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.8.0 Hybrid Rolling Hunt (phase 1)
#
# Goal: practical shiny hunting, not a claim of perfect prediction.
# - Keep the proven v7.6.7j physical-UP Exact2 + M14 Resume path unchanged.
# - PRE selector is only a coarse rolling pre-filter.
# - rel40 is authoritative for the second-stage score.
# - This first build is telemetry/non-terminal at rel40: no RNG/DIV/DV/input write,
#   no synthetic input, no automatic abort. It measures the score on real runs
#   before enabling hard gating in a later build.

P = Path('reader_core/src/crystal/practical.rs')
p = P.read_text()

# v7.6.0 used >=12 as an experimental pre-filter. Latest PRE->final LOO shows
# PRE-only concentration tops out below 10%, so use a deliberately permissive
# coarse threshold. rel40 remains the authoritative second stage.
p = rep(p,
        '    if score<12{return None}',
        '    if score<6{return None}',
        'coarse PRE threshold 12 -> 6')
P.write_text(p)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

old = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                if let Some(x)=g.prediction{
                    self.practical_empirical=x.lane_id>=101&&x.lane_id<200;
                    self.bucket_model_active=x.lane_id>=200;
                    self.rebind_practical_post_v690(x,post.proto,post.rot40);
                }
                // Do not make prediction support a condition for collecting the
                // actual tail. Generic probe/result detection remains active.
                self.practical_active=false;
                return
'''
new = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;

                // v7.8.0 Hybrid stage-2 score. This is a measured model-support
                // score at actual rel40, not a promised physical probability.
                // Store it in the existing practical support/mask fields so the
                // normal UI/CSV path records it without adding execution hooks.
                let hybrid_score:u8=if g.evaluated==0 {0} else {
                    (((g.shiny_models as u32)*100u32+(g.evaluated as u32)/2u32)/(g.evaluated as u32)).min(100u32) as u8
                };
                self.practical_support=hybrid_score;
                self.practical_mask=(g.shiny_models.min(255)) as u8;
                if let Some(x)=g.prediction{
                    self.practical_empirical=x.lane_id>=101&&x.lane_id<200;
                    self.bucket_model_active=x.lane_id>=200;
                    self.rebind_practical_post_v690(x,post.proto,post.rot40);
                    // rebind may restore the old support; rel40 Hybrid score is
                    // authoritative for v7.8.0 telemetry.
                    self.practical_support=hybrid_score;
                    self.practical_mask=(g.shiny_models.min(255)) as u8;
                }
                // Phase 1 intentionally never aborts here. Every candidate runs
                // to native final DV so score calibration has ground truth.
                self.practical_active=false;
                return
'''
t = rep(t, old, new, 'rel40 hybrid score telemetry')

t = t.replace('V767J', 'V780', 1) if 'V767J' in t else t
T.write_text(t)

print('Applied v7.8.0 Hybrid Rolling Hunt phase 1: PRE coarse filter + rel40 score telemetry; native final DV retained')
