#!/usr/bin/env python3
from pathlib import Path

P=Path('reader_core/src/crystal/practical.rs').read_text()
T=Path('reader_core/src/crystal/trace.rs').read_text()

def need(text,x,label):
    if x not in text: raise SystemExit('missing '+label)
def forbid(text,x,label):
    if x in text: raise SystemExit('forbidden '+label)

# Scanner architecture must remain v6.8 actual-root, not projected future search.
need(T,'fn practical_wait_monitor','actual-root monitor')
need(T,'if cur==self.practical_live_last_advance{return}','one evaluation per actionable current root')
need(T,'let state=reader.rng_state();let div=measured_div();','actual state/div capture')
need(T,'practical::evaluate_exact','exact proven current-root evaluator')
need(T,'practical::evaluate_empirical','empirical current-root evaluator')
need(T,'pnp::request_pause();return','immediate pause on current-root candidate')

# v7.1.3 cross-family rel40 rescue.
need(P,'pub fn prediction_pre','lane PRE getter')
need(P,'pub fn empirical_lane_for_pre_post','unique empirical pre/post lookup')
need(P,'pub fn evaluate_empirical_post','empirical suffix evaluator')
need(P,'ai40.wrapping_sub(41)','target index reconstruction')
need(T,'fn rebind_known_post_v713','shared rel40 cross resolver')
need(T,'practical::evaluate_post_exact','proven suffix rebind')
need(T,'practical::evaluate_empirical_post','empirical suffix rebind')
need(T,'self.practical_empirical=false;','proven-mode rebind flag')
need(T,'self.practical_empirical=true;','empirical-mode rebind flag')
need(T,'self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div)','rel40 shared resolver call')

# Existing hard guards/learning and telemetry remain intact.
need(T,'self.practical_expected716_state','rel716 hard guard')
need(T,'self.practical_expected717_state','rel717 hard guard')
need(T,"post.proto==b'D'&&post.rot40==15",'D/r15 learn fallback')
need(T,'STAGE3,V710','stage3 telemetry compatibility')
need(T,'BRANCH710,V710','branch telemetry compatibility')
need(T,'S713 SCAN','v713 scan UI')
need(T,'S713 READY UP+B','v713 READY UI')
need(T,'S713 LEARN D15','v713 LEARN UI')
forbid(T,'S712 ','stale v712 UI')

print('v7.1.3 AUDIT PASS: actual-root scanner retained; proven<->empirical rel40 cross-rebind enabled; hard guards intact')
