from pathlib import Path
P=Path('reader_core/src/crystal/practical.rs')
T=Path('reader_core/src/crystal/trace.rs')
p=P.read_text(); t=T.read_text()

# Generalize v7.6.0 evaluator so the future planner can rank weak-but-real
# shiny hypotheses while retaining the production >=12 gate wrapper.
old_sig='pub fn evaluate_weighted_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32)->Option<BucketPrediction>{'
if old_sig not in p:
    raise SystemExit('v760 evaluator signature missing')
p=p.replace(old_sig,'fn evaluate_weighted_bucket_min(bucket:u8,state:u16,div:u16,ai:u32,si:u32,min_score:u8)->Option<BucketPrediction>{',1)
old_gate='if score<12{return None}'
if old_gate not in p:
    raise SystemExit('v760 score gate missing')
p=p.replace(old_gate,'if score<min_score{return None}',1)
anchor='''    Some(BucketPrediction{prediction:pred,bucket,anchor:l.anchor,distance:best_d,radius:16,\n        post_proto:l.post_proto,post_rot:l.post_rot})\n}\n'''
if anchor not in p:
    raise SystemExit('v760 evaluator end missing')
append=r'''

pub fn evaluate_weighted_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32)->Option<BucketPrediction>{
    evaluate_weighted_bucket_min(bucket,state,div,ai,si,12)
}

#[derive(Clone, Copy)]
pub struct FutureBucketPrediction {
    pub bucket_prediction: BucketPrediction,
    pub delta_advance: u32,
    pub target_state: u16,
    pub target_div: u16,
    pub target_ap4: u16,
    pub target_sp4: u16,
    pub robust_count: u8,
}

// PRE prototype A, measured from exact lag-0 hardware rings. Starting from
// A/r10, the same slot returns every 16 ADV. Both VBlank DIV reads advance by
// the same LR35902 M-cycle delta; their fixed 11 M-cycle separation is already
// present in ap4/sp4.
const V761_PRE_A:[i16;16]=[1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1];
const V761_FRAME_M:i32=1172;

fn v761_better(a:&FutureBucketPrediction,b:&FutureBucketPrediction)->bool{
    let ap=a.bucket_prediction.prediction;
    let bp=b.bucket_prediction.prediction;
    if ap.support_weight!=bp.support_weight{return ap.support_weight>bp.support_weight}
    if a.robust_count!=b.robust_count{return a.robust_count>b.robust_count}
    if a.bucket_prediction.distance!=b.bucket_prediction.distance{return a.bucket_prediction.distance<b.bucket_prediction.distance}
    a.delta_advance<b.delta_advance
}

pub fn plan_future_a10(bucket0:u8,state0:u16,div0:u16,ap4_0:u16,sp4_0:u16,ai0:u32,si0:u32)->Option<FutureBucketPrediction>{
    let mut state=state0;
    let mut ap4=ap4_0&0x3fff;
    let mut sp4=sp4_0&0x3fff;
    let mut best:Option<FutureBucketPrediction>=None;
    // Search the complete +37 bucket orbit once: 256 A/r10 roots = 4096 ADV.
    for step in 1u32..=4096u32{
        let slot=((10u32+step-1)&15)as usize;
        let dm=(V761_FRAME_M + V761_PRE_A[slot] as i32) as u16;
        ap4=ap4.wrapping_add(dm)&0x3fff;
        sp4=sp4.wrapping_add(dm)&0x3fff;
        let div=(((ap4>>6)as u16)<<8)|((sp4>>6)as u16);
        state=upd(state,(div>>8)as u8,div as u8);
        if (step&15)!=0{continue}
        let k=step>>4;
        let bucket=bucket0.wrapping_add((37u32.wrapping_mul(k) & 0xff) as u8);
        // Loose floor=1 is only for ranking. The actual root is re-evaluated
        // from measured state/DIV after the target pause before Exact2F arms.
        if let Some(bp)=evaluate_weighted_bucket_min(bucket,state,div,ai0.wrapping_add(step),si0.wrapping_add(step),1){
            let robust=bp.prediction.shiny_mask.count_ones().min(255) as u8;
            let cand=FutureBucketPrediction{bucket_prediction:bp,delta_advance:step,target_state:state,target_div:div,target_ap4:ap4,target_sp4:sp4,robust_count:robust};
            match best{None=>best=Some(cand),Some(ref old)=>if v761_better(&cand,old){best=Some(cand)}}
        }
    }
    best
}
'''
p=p.replace(anchor,anchor+append,1)

# Replace live monitor: first exact A/r10 plans once; then normal gameplay runs
# toward the selected absolute ADV. No RNG/DIV/state is written.
a=t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
b=t.index('\n    fn practical_fail',a)
new_monitor=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if self.probe_session || self.practical_active { return; }
        let cur=rng_advance();

        // A future target is already bound: just navigate normal gameplay to it.
        if self.practical_live_found_lane==253 && self.practical_candidate_valid {
            if cur>self.practical_target {
                self.practical_miss=8; self.practical_live_scan=false; self.practical_scan_enabled=false;
                pnp::request_pause(); return;
            }
            if cur==self.practical_target {
                self.practical_live_scan=false; pre_vblank_timing_capture_stop(); pnp::request_pause();
            }
            return;
        }
        if !self.practical_scan_enabled || !self.practical_live_scan{return}
        let da=cur.wrapping_sub(self.practical_live_last_advance);
        if da==0{return}
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);
        self.bucket_scan_steps=self.bucket_scan_steps.saturating_add(da.min(0xffff));
        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN); if n!=PRE_VBLANK_RING_LEN{return}
        let(last,_)=pre_ring_sample(&r,n-1); let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best; self.phase_second_score=second; self.phase_consecutive=ok;
        self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag.min(255)as u8;
        if lag==1{rot=rot.wrapping_add(1)&15}
        if lag!=0 || !ok || best!=0{return}
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);
        if proto0!=b'A' || rot!=10{return}
        let(_,p0)=pre_ring_sample(&r,0); let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0{return}
        let bucket=((pd>>6)&0xff)as u8; self.bucket_current=bucket;
        let ai=add_div_tracker().index().unwrap_or(0)as u32;
        let si=sub_div_tracker().index().unwrap_or(0)as u32;
        if ai==0||si==0{return}
        let div=measured_div();
        let ap4=direct_phase_m((div>>8)as u8,adiv_subtick());
        let sp4=direct_phase_m(div as u8,sdiv_subtick());
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);
        if let Some(fp)=practical::plan_future_a10(bucket,reader.rng_state(),div,ap4,sp4,ai,si){
            let bp=fp.bucket_prediction; let p=bp.prediction;
            self.bucket_model_active=true; self.bucket_current=bp.bucket; self.bucket_anchor=bp.anchor;
            self.bucket_distance=bp.distance; self.bucket_radius=bp.radius;
            self.bucket_expected_post_proto=bp.post_proto; self.bucket_expected_post_rot=bp.post_rot;
            self.phase_target_proto=b'A'; self.phase_target_rot=10;
            self.practical_live_found_advance=cur; self.practical_live_found_state=fp.target_state;
            self.practical_live_found_div=fp.target_div; self.practical_live_found_tick=pnp::system_tick();
            self.practical_live_found_ai=ai.wrapping_add(fp.delta_advance); self.practical_live_found_si=si.wrapping_add(fp.delta_advance);
            self.practical_target=cur.wrapping_add(fp.delta_advance);
            self.practical_lane=p.lane_id; self.practical_source=p.source; self.practical_support=p.support_weight;
            self.practical_mask=p.shiny_mask; self.practical_raw=p.raw; self.practical_miss=0;
            self.practical_expected40_state=p.expected40_state; self.practical_expected40_div=p.expected40_div;
            self.practical_expected716_state=p.expected716_state; self.practical_expected716_div=p.expected716_div;
            self.practical_expected717_state=p.expected717_state; self.practical_expected717_div=p.expected717_div;
            self.practical_checked40=false; self.practical_checked716=false; self.practical_checked717=false;
            self.practical_live_found_lane=253; self.practical_candidate_valid=true; self.practical_empirical=false;
            self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);
            // Planner is finished, but keep live_root_monitor active as the navigator.
            self.practical_scan_enabled=false; self.practical_live_scan=true;
        }
    }
'''
t=t[:a]+new_monitor+t[b:]

# Replace control function. At the target, re-evaluate from actual measured
# state/DIV/index. This prevents a future-projection error from silently arming
# Exact2F. Score floor 1 is intentional: rel40 remains the authoritative gate.
a=t.index('    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {')
b=t.index('\n    pub fn status_line',a)
new_control=r'''    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {
        let mut out=0u32;
        if self.practical_live_found_lane==253 && self.practical_candidate_valid && !self.probe_session{out|=1u32<<31}
        let r=latest_pre_vblank_ring(); let count=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        let(proto,rot,best,second,consecutive)=classify_pre_ring(&r);
        self.phase_now_proto=proto; self.phase_now_rot=rot; self.phase_best_score=best;
        self.phase_second_score=second; self.phase_consecutive=consecutive;
        let cur=rng_advance();
        if self.practical_live_found_lane==253 && self.practical_candidate_valid && !self.probe_session && cur>self.practical_target{
            self.practical_miss=8; out|=1u32<<26; return out;
        }
        if count==PRE_VBLANK_RING_LEN && consecutive && best==0{
            out|=1u32<<29; out|=proto as u32; out|=(rot as u32)<<8;
            let(_,p0)=pre_ring_sample(&r,0); let pd=p0.wrapping_sub(0x0035)&0x3fff;
            if (pd&0x003f)==0{
                let bucket=((pd>>6)&0xff)as u8; out|=1u32<<28; out|=(bucket as u32)<<12;
                if self.practical_live_found_lane==253 && self.practical_candidate_valid && !self.probe_session
                    && cur==self.practical_target && proto==b'A' && rot==10{
                    let ai=add_div_tracker().index().unwrap_or(0)as u32;
                    let si=sub_div_tracker().index().unwrap_or(0)as u32;
                    if let Some(bp)=practical::evaluate_weighted_bucket_loose(bucket,reader.rng_state(),measured_div(),ai,si){
                        let p=bp.prediction;
                        self.bucket_current=bucket; self.bucket_anchor=bp.anchor; self.bucket_distance=bp.distance;
                        self.bucket_expected_post_proto=bp.post_proto; self.bucket_expected_post_rot=bp.post_rot;
                        self.practical_lane=p.lane_id; self.practical_source=p.source; self.practical_support=p.support_weight;
                        self.practical_mask=p.shiny_mask; self.practical_raw=p.raw;
                        self.practical_expected40_state=p.expected40_state; self.practical_expected40_div=p.expected40_div;
                        self.practical_expected716_state=p.expected716_state; self.practical_expected716_div=p.expected716_div;
                        self.practical_expected717_state=p.expected717_state; self.practical_expected717_div=p.expected717_div;
                        self.practical_live_found_state=reader.rng_state(); self.practical_live_found_div=measured_div();
                        self.practical_live_found_ai=ai; self.practical_live_found_si=si; self.practical_live_found_tick=pnp::system_tick();
                        out|=1u32<<27;
                    }else{
                        self.practical_miss=9; out|=1u32<<26;
                    }
                }
            }
        }
        out
    }
'''
t=t[:a]+new_control+t[b:]

# Public loose evaluator used only at the frozen target for actual rebind.
needle='''pub fn evaluate_weighted_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32)->Option<BucketPrediction>{\n    evaluate_weighted_bucket_min(bucket,state,div,ai,si,12)\n}\n'''
repl=needle+'''pub fn evaluate_weighted_bucket_loose(bucket:u8,state:u16,div:u16,ai:u32,si:u32)->Option<BucketPrediction>{\n    evaluate_weighted_bucket_min(bucket,state,div,ai,si,1)\n}\n'''
if needle not in p: raise SystemExit('wrapper insertion anchor missing')
p=p.replace(needle,repl,1)

# Weighted-model rel40 mismatch must attempt the already-proven known POST
# rebind before falling into LEARN.
old='''   if !ok{if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}\n'''
new='''   if !ok{if post.valid&&post.best_score==0&&self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}\n'''
if old not in t: raise SystemExit('weighted rel40 anchor missing')
t=t.replace(old,new,1)

# UI: distinguish navigation from the final frozen lock and expose distance.
old='''            } else if self.practical_candidate_valid && self.bucket_model_active {\n                pnp::println!("S760 WEIGHTED LOCK");\n                pnp::println!("SCORE {} T{}",self.practical_support,self.practical_target);\n                pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");\n'''
new='''            } else if self.practical_candidate_valid && self.bucket_model_active {\n                if rng_advance()<self.practical_target {\n                    pnp::println!("S761 FUTURE NAV");\n                    pnp::println!("NOW{} T{}",rng_advance(),self.practical_target);\n                    pnp::println!("LEFT {} SC{}",self.practical_target.wrapping_sub(rng_advance()),self.practical_support);\n                    pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                    pnp::println!("NORMAL PLAY - NO ARM");\n                } else {\n                    pnp::println!("S761 FUTURE LOCK");\n                    pnp::println!("SCORE {} T{}",self.practical_support,self.practical_target);\n                    pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                    pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                    pnp::println!("B -> RELEASE -> UP");\n                }\n'''
if old not in t: raise SystemExit('v760 UI lock anchor missing')
t=t.replace(old,new,1)
t=t.replace('pnp::println!("S760 TARGET MISSED");','pnp::println!("S761 TARGET BAD");',1)
t=t.replace('pnp::println!("S760 WEIGHTED SCAN");','pnp::println!("S761 FUTURE SEARCH");',1)

# CSV version marker.
t=t.replace('SELECTOR760,V760,','SELECTOR761,V761,',1)
t=t.replace('"selector,version,target_advance,model_score,model_mask,bucket,anchor,distance,expected_post_proto,expected_post_rot,pred_raw,miss\\nSELECTOR760,V760,',
            '"selector,version,target_advance,model_score,model_mask,bucket,anchor,distance,expected_post_proto,expected_post_rot,pred_raw,miss\\nSELECTOR761,V761,',1)

P.write_text(p); T.write_text(t)
print('applied v7.6.1 direct future selector')
