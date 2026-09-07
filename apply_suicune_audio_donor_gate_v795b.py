#!/usr/bin/env python3
from pathlib import Path

T=Path('reader_core/src/crystal/trace.rs')
t=T.read_text()

def replace_fn(src,sig,new):
    i=src.index(sig); b=src.index('{',i); depth=0; j=b
    while j < len(src):
        if src[j]=='{': depth+=1
        elif src[j]=='}':
            depth-=1
            if depth==0: return src[:i]+new+src[j+1:]
        j+=1
    raise SystemExit('v795b function end not found')

new_monitor=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        // v7.9.5b production scope is deliberately narrow: every AudioPRE
        // donor 0004-0014 was measured from an exact A/r10 bucket76 root,
        // followed by the fixed neutral 3F transport. Do not extrapolate the
        // donor transport to other PRE cells or buckets.
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid
        { return; }

        let cur=rng_advance();
        let da=cur.wrapping_sub(self.practical_live_last_advance);
        if da==0 { return; }
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);

        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n!=PRE_VBLANK_RING_LEN { return; }
        let (last,_)=pre_ring_sample(&r,n-1);
        let lag=cur.wrapping_sub(last);
        let (proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best;
        self.phase_second_score=second;
        self.phase_consecutive=ok;
        self.phase_now_proto=proto0;
        self.phase_now_rot=rot;
        self.phase_now_lag=lag.min(255) as u8;
        if lag==1 { rot=rot.wrapping_add(1)&15; }
        if lag!=0 || !ok || best!=0 { return; }
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);
        self.phase_now_rot=rot;
        if proto0!=b'A' || rot!=10 { return; }

        let (_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0 { return; }
        let bucket=((pd>>6)&0xff) as u8;
        self.bucket_current=bucket;
        if bucket!=76 { return; }

        let Some(ai0)=add_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let Some(si0)=sub_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let ai=(ai0 as u32)&0x3fff;
        let si=(si0 as u32)&0x3fff;

        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);
        let Some(bp)=practical::evaluate_weighted_bucket(
            bucket,reader.rng_state(),measured_div(),ai,si
        ) else { return; };

        self.phase_target_proto=b'A';
        self.phase_target_rot=10;
        self.multipre_score=bp.prediction.support_weight;
        self.multipre_branches=bp.prediction.shiny_mask.count_ones().min(255) as u8;
        self.bucket_model_active=true;
        self.bucket_current=bucket;
        self.bucket_anchor=bp.anchor;
        self.bucket_distance=bp.distance;
        self.bucket_radius=bp.radius;
        self.bucket_expected_post_proto=bp.post_proto;
        self.bucket_expected_post_rot=bp.post_rot;

        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai;
        self.practical_live_found_si=si;
        self.bind_practical_prediction(bp.prediction);
        self.practical_live_found_lane=253;
        self.practical_empirical=false;
        self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);
        self.practical_live_scan=false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }'''

t=replace_fn(t,'    fn live_root_monitor(&mut self, reader: &Gen2Reader)',new_monitor)
T.write_text(t)
print('Applied v7.9.5b: production shiny scan restricted to measured A/r10 bucket76 donor domain')
