from pathlib import Path
P=Path('reader_core/src/crystal/practical.rs')
T=Path('reader_core/src/crystal/trace.rs')
M=Path('3gx/sources/main.c')
p=P.read_text(); t=T.read_text(); m=M.read_text()

def rep(src,old,new,msg):
    n=src.count(old)
    if n!=1: raise SystemExit(f'{msg}: expected 1 got {n}')
    return src.replace(old,new,1)

append=r'''

// v7.6.0 Weighted Future Root Selector.
// PRE A/r10 repeats every 16 advances. Starting from an exact A/r10 root,
// project the next 255 legal roots from the live A/S divider phases and the
// proven 16-period PRE prototype. No game memory is written.
#[derive(Clone, Copy, Default)]
pub struct WeightedBucketPrediction {
    pub prediction: Prediction,
    pub bucket: u8,
    pub anchor: u8,
    pub distance: u8,
    pub post_proto: u8,
    pub post_rot: u8,
    pub score: u16,
    pub shiny_models: u8,
}

#[derive(Clone, Copy, Default)]
pub struct FutureRootPrediction {
    pub delta_advance: u32,
    pub root_index: u16,
    pub state: u16,
    pub div: u16,
    pub phase_a: u16,
    pub phase_s: u16,
    pub weighted: WeightedBucketPrediction,
}

const V760_PRE_A:[i16;16]=[1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1];

fn v760_lane_eval(l:&BucketLane,bucket:u8,state:u16,div:u16)->Option<WeightedBucketPrediction>{
    let d=bucket_cdist(bucket,l.anchor);
    if d>64{return None}
    let av=(div>>8)as u8; let sv=div as u8;
    let pre=apply_sums(state,l.full_a[av as usize],l.full_s[sv as usize]);
    let la=av.wrapping_add(l.last_a); let ls=sv.wrapping_add(l.last_s);
    let mut raw=0u16; let mut mask=0u8; let mut evidence=0u16; let mut models=0u8;
    let mut st=pre; let mut q=[0u8;3];
    for j in 0..3usize{st=upd(st,la.wrapping_add(l.primary_a[j]),ls.wrapping_add(l.primary_s[j]));q[j]=st as u8;}
    if q[0]<0xc0{
        let v=((q[1]as u16)<<8)|q[2]as u16;
        if shiny(v){raw=v;mask|=0x80;evidence=evidence.saturating_add(4);models=models.saturating_add(1);}
    }
    for i in 0..5usize{
        if DEEP_A[i]==l.primary_a && DEEP_S[i]==l.primary_s{continue}
        let mut st=pre;let mut q=[0u8;3];
        for j in 0..3usize{st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));q[j]=st as u8;}
        if q[0]>=0xc0{continue}
        let v=((q[1]as u16)<<8)|q[2]as u16;
        if shiny(v){if raw==0{raw=v} mask|=1u8<<i;evidence=evidence.saturating_add(DEEP_WEIGHT[i]as u16);models=models.saturating_add(1);}
    }
    if raw==0{return None}
    let proximity=(65u16).saturating_sub(d as u16);
    let score=evidence.saturating_mul(proximity);
    let pred=Prediction{lane_id:l.id,source:l.source,support_weight:evidence.min(255)as u8,shiny_mask:mask,raw,
        expected40_state:apply_sums(state,l.p40_a[av as usize],l.p40_s[sv as usize]),
        expected40_div:((av.wrapping_add(l.o40a)as u16)<<8)|sv.wrapping_add(l.o40s)as u16,
        expected716_state:apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]),
        expected716_div:((av.wrapping_add(l.o716a)as u16)<<8)|sv.wrapping_add(l.o716s)as u16,
        expected717_state:{let s716=apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]);let d717=((av.wrapping_add(l.o717a)as u16)<<8)|sv.wrapping_add(l.o717s)as u16;upd(s716,(d717>>8)as u8,d717 as u8)},
        expected717_div:((av.wrapping_add(l.o717a)as u16)<<8)|sv.wrapping_add(l.o717s)as u16};
    Some(WeightedBucketPrediction{prediction:pred,bucket,anchor:l.anchor,distance:d,post_proto:l.post_proto,post_rot:l.post_rot,score,shiny_models:models})
}

pub fn evaluate_weighted_bucket(bucket:u8,state:u16,div:u16)->Option<WeightedBucketPrediction>{
    let mut best:Option<WeightedBucketPrediction>=None;
    let mut aggregate=0u16;
    for l in BUCKET_LANES.iter(){
        if let Some(w)=v760_lane_eval(l,bucket,state,div){
            aggregate=aggregate.saturating_add(w.score);
            if best.map_or(true,|b|w.score>b.score || (w.score==b.score && w.distance<b.distance)){best=Some(w);}
        }
    }
    let mut b=best?;
    b.score=aggregate;
    Some(b)
}

fn v760_step_phase(phase:u16,residual:i16)->u16{
    ((phase as i32 + 1172 + residual as i32)&0x3fff)as u16
}

pub fn search_future_weighted(state0:u16,phase_a0:u16,phase_s0:u16,bucket0:u8,max_roots:u16,min_roots:u16)->Option<FutureRootPrediction>{
    let mut state=state0; let mut pa=phase_a0; let mut ps=phase_s0; let mut bucket=bucket0;
    let mut best:Option<FutureRootPrediction>=None;
    let lim=max_roots.min(255);
    for root in 1..=lim{
        for i in 0..16usize{
            let r=V760_PRE_A[(10+i)&15];
            pa=v760_step_phase(pa,r); ps=v760_step_phase(ps,r);
            state=upd(state,(pa>>6)as u8,(ps>>6)as u8);
        }
        bucket=bucket.wrapping_add(37);
        if root<min_roots{continue}
        let div=((pa>>6)<<8)|(ps>>6);
        if let Some(w)=evaluate_weighted_bucket(bucket,state,div){
            let candidate=FutureRootPrediction{delta_advance:(root as u32)*16,root_index:root,state,div,phase_a:pa,phase_s:ps,weighted:w};
            if best.map_or(true,|b|candidate.weighted.score>b.weighted.score || (candidate.weighted.score==b.weighted.score && candidate.delta_advance<b.delta_advance)){best=Some(candidate);}
        }
    }
    best
}
'''
p += append
P.write_text(p)

old='''    bucket_expected_post_proto: u8,\n    bucket_expected_post_rot: u8,\n    turbo_a10_count: u16,'''
new='''    bucket_expected_post_proto: u8,\n    bucket_expected_post_rot: u8,\n    selector_nav_active: bool,\n    selector_target_advance: u32,\n    selector_pause_request_advance: u32,\n    selector_freeze_advance: u32,\n    selector_expected_bucket: u8,\n    selector_expected_state: u16,\n    selector_expected_div: u16,\n    selector_score: u16,\n    selector_models: u8,\n    selector_root_index: u16,\n    selector_actual_score: u16,\n    selector_overshoot: bool,\n    turbo_a10_count: u16,'''
t=rep(t,old,new,'trace fields')
old='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            turbo_a10_count: 0,'''
new='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            selector_nav_active: false,\n            selector_target_advance: 0,\n            selector_pause_request_advance: 0,\n            selector_freeze_advance: 0,\n            selector_expected_bucket: 0,\n            selector_expected_state: 0,\n            selector_expected_div: 0,\n            selector_score: 0,\n            selector_models: 0,\n            selector_root_index: 0,\n            selector_actual_score: 0,\n            selector_overshoot: false,\n            turbo_a10_count: 0,'''
t=rep(t,old,new,'trace defaults')
old='''        self.practical_rebound = false;\n        pre_vblank_timing_capture_start();'''
new='''        self.practical_rebound = false;\n        self.selector_nav_active=false;\n        self.selector_target_advance=0;\n        self.selector_pause_request_advance=0;\n        self.selector_freeze_advance=0;\n        self.selector_expected_bucket=0;\n        self.selector_expected_state=0;\n        self.selector_expected_div=0;\n        self.selector_score=0;\n        self.selector_models=0;\n        self.selector_root_index=0;\n        self.selector_actual_score=0;\n        self.selector_overshoot=false;\n        pre_vblank_timing_capture_start();'''
t=rep(t,old,new,'start reset')

start=t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
end=t.index('\n    fn practical_fail',start)
newfn=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        const NAV_GUARD:u32=64;
        if !self.practical_scan_enabled || !self.practical_live_scan || self.probe_session || self.practical_active { return; }
        let cur=rng_advance();
        if self.selector_nav_active {
            if cur>=self.selector_target_advance.saturating_sub(NAV_GUARD) {
                self.selector_pause_request_advance=cur;
                self.practical_live_found_advance=self.selector_target_advance;
                self.practical_live_found_lane=253;
                self.practical_live_scan=false;
                pnp::request_pause();
            }
            return;
        }
        if cur==self.practical_live_last_advance{return}
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);
        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n!=PRE_VBLANK_RING_LEN{return}
        let(last,_)=pre_ring_sample(&r,n-1);
        let lag=cur.wrapping_sub(last);
        let(proto0,rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best;self.phase_second_score=second;self.phase_consecutive=ok;
        self.phase_now_proto=proto0;self.phase_now_rot=rot;self.phase_now_lag=lag.min(255)as u8;
        if lag!=0 || !ok || best!=0 || proto0!=b'A' || rot!=10{return}
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);
        let(_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0{return}
        let bucket=((pd>>6)&0xff)as u8;
        self.bucket_current=bucket;
        let div=measured_div();
        let pa=direct_phase_m((div>>8)as u8,adiv_subtick());
        let ps=direct_phase_m(div as u8,sdiv_subtick());
        if let Some(f)=practical::search_future_weighted(reader.rng_state(),pa,ps,bucket,255,8){
            self.selector_nav_active=true;
            self.selector_target_advance=cur.wrapping_add(f.delta_advance);
            self.selector_expected_bucket=f.weighted.bucket;
            self.selector_expected_state=f.state;
            self.selector_expected_div=f.div;
            self.selector_score=f.weighted.score;
            self.selector_models=f.weighted.shiny_models;
            self.selector_root_index=f.root_index;
            self.bucket_anchor=f.weighted.anchor;
            self.bucket_distance=f.weighted.distance;
            self.bucket_expected_post_proto=f.weighted.post_proto;
            self.bucket_expected_post_rot=f.weighted.post_rot;
            self.practical_lane=f.weighted.prediction.lane_id;
            self.practical_source=f.weighted.prediction.source;
            self.practical_support=f.weighted.prediction.support_weight;
            self.practical_mask=f.weighted.prediction.shiny_mask;
            self.practical_raw=f.weighted.prediction.raw;
        }
    }
'''
t=t[:start]+newfn+t[end:]

needle='''        if cur!=self.bucket_control_last_advance {\n            self.bucket_control_last_advance=cur;'''
insert='''        if self.selector_nav_active && self.practical_live_found_lane==253 && !self.probe_session {\n            out|=1u32<<31;\n            if self.selector_freeze_advance==0 { self.selector_freeze_advance=cur; }\n            if cur>self.selector_target_advance { self.selector_overshoot=true; self.practical_miss=5; out|=1u32<<26; return out; }\n        }\n'''
t=rep(t,needle,insert+needle,'selector pause prelude')
old='''                if proto==b'A' && rot==10 && self.practical_live_found_lane==253 && !self.probe_session {\n                    self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);\n                    if let Some(bp)=practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_div_tracker().index().unwrap_or(0) as u32,sub_div_tracker().index().unwrap_or(0) as u32,self.bucket_scan_steps) {\n                        self.bucket_model_active=true;\n                        self.bucket_anchor=bp.anchor;\n                        self.bucket_distance=bp.distance;\n                        self.bucket_radius=bp.radius;\n                        self.bucket_expected_post_proto=bp.post_proto;\n                        self.bucket_expected_post_rot=bp.post_rot;\n                        self.phase_target_proto=proto; self.phase_target_rot=rot;\n                        self.practical_live_found_advance=cur;\n                        self.practical_live_found_state=reader.rng_state();\n                        self.practical_live_found_div=measured_div();\n                        self.practical_live_found_tick=pnp::system_tick();\n                        self.practical_live_found_ai=add_div_tracker().index().unwrap_or(0) as u32;\n                        self.practical_live_found_si=sub_div_tracker().index().unwrap_or(0) as u32;\n                        self.bind_practical_prediction(bp.prediction);\n                        self.practical_empirical=false;\n                        self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);\n                        out|=1u32<<27;\n                    }\n                }'''
new='''                if proto==b'A' && rot==10 && self.practical_live_found_lane==253 && !self.probe_session {\n                    if self.selector_nav_active {\n                        if cur==self.selector_target_advance {\n                            self.bucket_current=bucket;\n                            if bucket!=self.selector_expected_bucket { self.practical_miss=6; out|=1u32<<26; return out; }\n                            if let Some(w)=practical::evaluate_weighted_bucket(bucket,reader.rng_state(),measured_div()) {\n                                self.selector_actual_score=w.score;\n                                self.bucket_model_active=true;self.bucket_anchor=w.anchor;self.bucket_distance=w.distance;\n                                self.bucket_expected_post_proto=w.post_proto;self.bucket_expected_post_rot=w.post_rot;\n                                self.phase_target_proto=proto;self.phase_target_rot=rot;\n                                self.practical_live_found_advance=cur;self.practical_live_found_state=reader.rng_state();self.practical_live_found_div=measured_div();\n                                self.practical_live_found_tick=pnp::system_tick();\n                                self.bind_practical_prediction(w.prediction);\n                                self.practical_target=cur;\n                                self.selector_nav_active=false;\n                                out|=1u32<<27;\n                            } else { self.practical_miss=7; out|=1u32<<26; return out; }\n                        }\n                    } else {\n                        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);\n                        if let Some(bp)=practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_div_tracker().index().unwrap_or(0) as u32,sub_div_tracker().index().unwrap_or(0) as u32,self.bucket_scan_steps) {\n                            self.bucket_model_active=true;self.bucket_anchor=bp.anchor;self.bucket_distance=bp.distance;self.bucket_radius=bp.radius;\n                            self.bucket_expected_post_proto=bp.post_proto;self.bucket_expected_post_rot=bp.post_rot;\n                            self.phase_target_proto=proto;self.phase_target_rot=rot;self.practical_live_found_advance=cur;\n                            self.practical_live_found_state=reader.rng_state();self.practical_live_found_div=measured_div();self.practical_live_found_tick=pnp::system_tick();\n                            self.practical_live_found_ai=add_div_tracker().index().unwrap_or(0) as u32;self.practical_live_found_si=sub_div_tracker().index().unwrap_or(0) as u32;\n                            self.bind_practical_prediction(bp.prediction);self.practical_empirical=false;self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);out|=1u32<<27;\n                        }\n                    }\n                }'''
t=rep(t,old,new,'target-only lane253')
old='''        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            if self.practical_candidate_valid && self.bucket_model_active {\n                pnp::println!("S738 SHINY LOCK");\n                pnp::println!("B{} A{} D{} R{}",self.bucket_current,self.bucket_anchor,self.bucket_distance,self.bucket_radius);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B ARM -> UP");\n            } else {\n                pnp::println!("S738 CONF SHINY SCAN");\n                if self.phase_now_proto==b'?' { pnp::println!("NOW ?"); }\n                else { pnp::println!("NOW {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current); }\n                pnp::println!("N{} R{}",self.bucket_scan_steps,self.bucket_radius);\n                pnp::println!("AUTO NEUTRAL - NO INPUT");\n            }\n'''
new='''        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            if self.practical_candidate_valid && self.bucket_model_active {\n                pnp::println!("S760 TARGET LOCK");\n                pnp::println!("ADV{} B{} SC{}",self.practical_target,self.bucket_current,self.selector_actual_score);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");\n            } else if self.practical_miss!=0 {\n                pnp::println!("S760 NAV FAIL {}",self.practical_miss);pnp::println!("RESET VC");\n            } else {\n                pnp::println!("S760 LANDING");\n                pnp::println!("TARGET {}",self.selector_target_advance);\n                pnp::println!("FREEZE {}",self.selector_freeze_advance);\n                pnp::println!("AUTO NEUTRAL");\n            }\n'''
t=rep(t,old,new,'status lane253')
old='''        } else if self.practical_live_found_lane == 250 && !self.probe_session {'''
new='''        } else if self.selector_nav_active && self.practical_live_found_lane != 253 && !self.probe_session {\n            let cur=rng_advance(); let rem=self.selector_target_advance.saturating_sub(cur);\n            pnp::println!("S760 SHINY SELECTOR");\n            pnp::println!("NOW{} -> {} (+{})",cur,self.selector_target_advance,rem);\n            pnp::println!("B{} SC{} M{}",self.selector_expected_bucket,self.selector_score,self.selector_models);\n            pnp::println!("NO INPUT / LEGAL ADV");\n        } else if self.practical_live_found_lane == 250 && !self.probe_session {'''
t=rep(t,old,new,'selector scan status')
needle='''        let mut line = LineBuf::new();\n'''
insert='''        let mut line = LineBuf::new();\n        let _=write!(line,"selector,version,target_adv,pause_request_adv,freeze_adv,expected_bucket,expected_state,expected_div,projected_score,actual_score,models,root_index,overshoot,raw\\nSELECT,V760,{},{},{},{},{:04X},{:04X},{},{},{},{},{},{:04X}\\n\\n",self.selector_target_advance,self.selector_pause_request_advance,self.selector_freeze_advance,self.selector_expected_bucket,self.selector_expected_state,self.selector_expected_div,self.selector_score,self.selector_actual_score,self.selector_models,self.selector_root_index,self.selector_overshoot as u8,self.practical_raw);\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n'''
t=rep(t,needle,insert,'selector telemetry')
T.write_text(t)

old='''            bool shiny_ready = (cell & 0x08000000U) != 0;\n            suicune_root_lock_last_cell = cell;'''
new='''            bool shiny_ready = (cell & 0x08000000U) != 0;\n            bool nav_failed = (cell & 0x04000000U) != 0;\n            suicune_root_lock_last_cell = cell;\n            if (nav_failed) { suicune_root_lock_failed = true; suicune_root_lock_active = false; continue; }'''
m=rep(m,old,new,'main nav fail')
old='''            if (just_pressed & (KEY_DDOWN | KEY_DUP | KEY_DLEFT | KEY_DRIGHT))\n            {\n                suicune_root_lock_active = false;\n                suicune_root_lock_ready = false;\n                suicune_root_lock_failed = false;\n                suicune_wait_up_after_b = false;\n                suicune_root_lock_steps = 0;\n                suicune_root_lock_last_cell = 0;\n                if (just_pressed & KEY_DDOWN) suicune_phase_slot = 12U; // IDLE\n                else if (just_pressed & KEY_DUP) suicune_phase_slot = 13U; // UP HOLD\n                else if (just_pressed & KEY_DLEFT) suicune_phase_slot = 14U; // B MASH\n                else suicune_phase_slot = 15U; // MENU IDLE\n                search_suicune_practical_targets();\n                is_paused = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                suicune_auto_resume_pending = false;\n                suicune_phase_lock_active = false;\n                break;\n            }\n            // Stage3 current-root live scan start.\n            if (just_pressed & KEY_DDOWN)'''
new='''            // v7.6.0 Y+DOWN starts the weighted future-root selector.\n            // Other Y+direction benchmark shortcuts are intentionally removed from this build.\n            if (just_pressed & KEY_DDOWN)'''
m=rep(m,old,new,'remove benchmark intercept')
M.write_text(m)
print('Applied Suicune v7.6.0 weighted future-root selector')
