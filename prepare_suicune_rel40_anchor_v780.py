from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# v7.6.7h intentionally changed the v7.6.6 terminal rel40 block into a
# non-terminal diagnostic continuation.  v7.8.0 replaces only the terminal
# decision tail, so normalize that exact generated block back to the v7.6.6
# anchor immediately before applying v780.  This is generation-only surgery;
# the final v780 block remains non-terminal on HIGH and terminal only on SKIP.
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
                // v7.6.6 ends every diagnostic run at rel40 after recording the
                // actual POST/J/state/div and suffix-gate support.  This avoids a
                // 700-frame tail and makes each M replicate fast and comparable.
                self.practical_fail(13);return
'''
if t.count(old) != 1:
    raise SystemExit(f'v780 normalize rel40 anchor count {t.count(old)}')
t = t.replace(old, new, 1)
T.write_text(t)
print('Normalized v7.6.7h rel40 continuation for v7.8.0 replacement')
