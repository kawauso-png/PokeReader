from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
M=Path('3gx/sources/main.c')
t=T.read_text();m=M.read_text()

def replace_fn(src,sig,new):
    i=src.index(sig);brace=src.index('{',i);depth=0;j=brace
    while j<len(src):
        if src[j]=='{':depth+=1
        elif src[j]=='}':
            depth-=1
            if depth==0:return src[:i]+new+src[j+1:]
        j+=1
    raise RuntimeError(sig)

new_monitor=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        let cur=rng_advance();
        // Once a future root is selected, never migrate to another root.
        if self.practical_live_found_lane==253&&self.practical_candidate_valid&&!self.probe_session{
            if cur>self.practical_target{
                self.practical_miss=8;self.practical_live_scan=false;pnp::request_pause();return
            }
            if cur<self.practical_target{return}
            let r=latest_pre_vblank_ring();let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);if n!=PRE_VBLANK_RING_LEN{return}
            let(last,_)=pre_ring_sample(&r,n-1);let lag=cur.wrapping_sub(last);
            let(proto,rot,best,_,ok)=classify_pre_ring(&r);
            if lag!=0||!ok||best!=0||proto!=b'A'||rot!=10{return}
            // Future projection must match the real frozen root before Exact2F.
            if reader.rng_state()!=self.practical_live_found_state||measured_div()!=self.practical_live_found_div{
                self.practical_miss=9;self.practical_live_scan=false;pnp::request_pause();return
            }
            self.practical_live_found_tick=pnp::system_tick();self.practical_live_scan=false;
            pre_vblank_timing_capture_stop();pnp::request_pause();return
        }
        if !self.practical_scan_enabled||!self.practical_live_scan||self.probe_session||self.practical_active||self.practical_candidate_valid{return}
        let da=cur.wrapping_sub(self.practical_live_last_advance);if da==0{return}
        self.practical_live_last_advance=cur;self.practical_live_checked=self.practical_live_checked.saturating_add(1);
        let r=latest_pre_vblank_ring();let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);if n!=PRE_VBLANK_RING_LEN{return}
        let(last,_)=pre_ring_sample(&r,n-1);let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best;self.phase_second_score=second;self.phase_consecutive=ok;self.phase_now_proto=proto0;self.phase_now_rot=rot;self.phase_now_lag=lag.min(255)as u8;
        if lag==1{rot=rot.wrapping_add(1)&15}
        if lag!=0||!ok||best!=0{return}
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);
        if proto0!=b'A'||rot!=10{return}
        let(_,p0)=pre_ring_sample(&r,0);let pd=p0.wrapping_sub(0x0035)&0x3fff;if(pd&0x003f)!=0{return}
        let bucket=((pd>>6)&0xff)as u8;self.bucket_current=bucket;
        let ai=add_div_tracker().index().unwrap_or(0)as u32;let si=sub_div_tracker().index().unwrap_or(0)as u32;
        if ai==0||si==0{self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);return}
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);
        let Some(fp)=practical::select_future_weighted_a10(bucket,reader.rng_state(),measured_div(),ai,si)else{return};
        let bp=fp.bucket_prediction;
        self.bucket_model_active=true;self.bucket_anchor=bp.anchor;self.bucket_distance=bp.distance;self.bucket_radius=bp.radius;
        self.bucket_expected_post_proto=bp.post_proto;self.bucket_expected_post_rot=bp.post_rot;self.bucket_current=bp.bucket;
        self.phase_target_proto=b'A';self.phase_target_rot=10;
        self.practical_live_found_advance=cur.wrapping_add(fp.delta_adv);self.practical_live_found_state=fp.target_state;self.practical_live_found_div=fp.target_div;
        self.practical_live_found_tick=0;self.practical_live_found_ai=fp.target_ai;self.practical_live_found_si=fp.target_si;
        self.bind_practical_prediction(bp.prediction);self.practical_target=self.practical_live_found_advance;
        self.practical_live_found_lane=253;self.practical_empirical=false;self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);
        self.practical_live_scan=true;
    }'''
t=replace_fn(t,'    fn live_root_monitor(&mut self, reader: &Gen2Reader)',new_monitor)

new_control=r'''    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {
        let mut out=0u32;
        if self.practical_live_found_lane==253&&self.practical_candidate_valid&&!self.probe_session{out|=1u32<<31}
        let r=latest_pre_vblank_ring();let count=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        let(proto,rot,best,second,consecutive)=classify_pre_ring(&r);
        self.phase_now_proto=proto;self.phase_now_rot=rot;self.phase_best_score=best;self.phase_second_score=second;self.phase_consecutive=consecutive;
        let cur=rng_advance();
        if self.practical_live_found_lane==253&&self.practical_candidate_valid&&!self.probe_session{
            if self.practical_miss==8||self.practical_miss==9||cur>self.practical_target{if self.practical_miss==0{self.practical_miss=8}out|=1u32<<26;return out}
        }
        if count==PRE_VBLANK_RING_LEN&&consecutive&&best==0{
            out|=1u32<<29;out|=proto as u32;out|=(rot as u32)<<8;
            let(_,p0)=pre_ring_sample(&r,0);let pd=p0.wrapping_sub(0x0035)&0x3fff;
            if(pd&0x003f)==0{
                let bucket=((pd>>6)&0xff)as u8;out|=1u32<<28;out|=(bucket as u32)<<12;
                if self.practical_live_found_lane==253&&self.practical_candidate_valid&&!self.probe_session&&cur==self.practical_target&&proto==b'A'&&rot==10{
                    if reader.rng_state()!=self.practical_live_found_state||measured_div()!=self.practical_live_found_div{self.practical_miss=9;out|=1u32<<26;return out}
                    self.bucket_current=bucket;self.phase_target_proto=proto;self.phase_target_rot=rot;self.practical_live_found_tick=pnp::system_tick();out|=1u32<<27;
                }
            }
        }
        out
    }'''
t=replace_fn(t,'    pub fn control_pause_cell(&mut self, reader: &Gen2Reader)',new_control)

old='''   if !ok{if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}\n'''
new='''   if !ok{\n    if post.valid&&post.best_score==0{\n     if let Some(x)=practical::evaluate_bucket_post_weighted(post.proto,post.rot40,e.state,e.div){self.practical_empirical=false;self.rebind_practical_post_v690(x,post.proto,post.rot40);return}\n     if self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div){return}\n     if practical::bucket_post_known(post.proto,post.rot40){self.practical_fail(7);return}\n     self.enter_stage3_learn(post.proto,post.rot40)\n    }else{self.practical_fail(1)}\n    return\n   }\n'''
if old not in t:raise SystemExit('weighted rel40 anchor missing')
t=t.replace(old,new,1)

old='''        if self.practical_scan_enabled {\n            pnp::println!("S760 WEIGHTED SCAN");\n            pnp::println!("ADV{} ROOT{}",rng_advance(),self.practical_live_checked);\n            if self.phase_now_proto==b'?' {pnp::println!("PRE ?");} else {pnp::println!("PRE {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current);}\n            pnp::println!("Y+DOWN START / IDLE");\n'''
new='''        if self.practical_scan_enabled {\n            pnp::println!("S761 FUTURE SCAN");\n            pnp::println!("ADV{} ROOT{}",rng_advance(),self.practical_live_checked);\n            if self.phase_now_proto==b'?' {pnp::println!("PRE ?");} else {pnp::println!("PRE {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current);}\n            pnp::println!("WINDOW +4096 ADV");\n'''
if old not in t:raise SystemExit('scan UI anchor missing')
t=t.replace(old,new,1)

old='''        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            if self.practical_miss==8 {\n                pnp::println!("S760 TARGET MISSED");\n                pnp::println!("T{} NOW{}",self.practical_target,rng_advance());\n                pnp::println!("RESET VC");\n            } else if self.practical_candidate_valid && self.bucket_model_active {\n                pnp::println!("S760 WEIGHTED LOCK");\n                pnp::println!("SCORE {} T{}",self.practical_support,self.practical_target);\n                pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");\n            } else {\n                pnp::println!("S760 LOCK WAIT");\n            }\n'''
new='''        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            if self.practical_miss==8 {\n                pnp::println!("S761 TARGET MISSED");pnp::println!("T{} NOW{}",self.practical_target,rng_advance());pnp::println!("RESET VC");\n            } else if self.practical_miss==9 {\n                pnp::println!("S761 PRED DRIFT");pnp::println!("T{} NOW{}",self.practical_target,rng_advance());pnp::println!("RESET VC");\n            } else if self.practical_candidate_valid&&self.bucket_model_active&&rng_advance()<self.practical_target {\n                pnp::println!("S761 NAV +{}",self.practical_target.wrapping_sub(rng_advance()));\n                pnp::println!("SCORE {} T{}",self.practical_support,self.practical_target);\n                pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                pnp::println!("NO INPUT - AUTO PAUSE");\n            } else if self.practical_candidate_valid&&self.bucket_model_active {\n                pnp::println!("S761 FUTURE LOCK");pnp::println!("SCORE {} T{}",self.practical_support,self.practical_target);\n                pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");\n            } else {pnp::println!("S761 LOCK WAIT");}\n'''
if old not in t:raise SystemExit('lane253 UI anchor missing')
t=t.replace(old,new,1)
t=t.replace('SELECTOR760,V760,','SELECTOR761,V761,',1)
m=m.replace('v7.6.0 production selector: Y+DOWN only.','v7.6.1 future selector: Y+DOWN only.')
T.write_text(t);M.write_text(m)
