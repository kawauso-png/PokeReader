from pathlib import Path
P=Path('reader_core/src/crystal/practical.rs')
T=Path('reader_core/src/crystal/trace.rs')
M=Path('3gx/sources/main.c')
p=P.read_text(); t=T.read_text(); m=M.read_text()

def replace_fn(src, sig, new):
    i=src.index(sig)
    brace=src.index('{',i); depth=0; j=brace
    while j<len(src):
        if src[j]=='{': depth+=1
        elif src[j]=='}':
            depth-=1
            if depth==0:
                return src[:i]+new+src[j+1:]
        j+=1
    raise RuntimeError(sig)

weighted=r'''
// v7.6.0 Weighted Root Selector.  This is a ranking model, not a claimed
// physical probability.  All five exact2F bucket donors are retained as
// competing branch hypotheses; deep-profile weights are updated from the
// 0124-0140 exact2F corpus, with P0/P0 dominant.  No game memory is written.
const W760_A:[[u8;3];8]=[
 [183,189,191], // P0
 [183,189,191], // P0 / S=P3
 [184,189,191], // P3
 [183,188,190], // P1 / S=P0
 [183,188,190], // P1
 [184,189,191], // P3 / S=P0 fallback
 [183,189,191], // P0 / S=P1 fallback
 [184,190,192], // P2 fallback
];
const W760_S:[[u8;3];8]=[
 [183,189,191],
 [184,189,191],
 [184,189,191],
 [183,189,191],
 [183,188,190],
 [183,189,191],
 [183,188,190],
 [184,190,192],
];
const W760_W:[u8;8]=[8,3,1,1,1,1,1,1];
fn w760_lane_weight(d:u8)->u32 {
    if d==0 {16} else if d<=4 {12} else if d<=8 {8} else if d<=16 {4} else {0}
}
fn w760_primary_is_listed(a:[u8;3],s:[u8;3])->bool{
    for i in 0..W760_A.len(){if W760_A[i]==a && W760_S[i]==s{return true}}
    false
}
pub fn evaluate_weighted_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32)->Option<BucketPrediction>{
    if ai==0 || si==0 || !empirical_window_safe(ai,si){return None}
    let av=(div>>8)as u8; let sv=div as u8;
    let mut total=0u32; let mut shiny_weight=0u32; let mut shiny_mask=0u8;
    let mut best_contrib=0u32; let mut best_raw=0u16; let mut best_idx=0usize;
    let mut best_d=0xffu8;
    for (li,l) in BUCKET_LANES.iter().enumerate(){
        let d=bucket_cdist(bucket,l.anchor); let lw=w760_lane_weight(d); if lw==0{continue}
        let pre=apply_sums(state,l.full_a[av as usize],l.full_s[sv as usize]);
        let la=av.wrapping_add(l.last_a); let ls=sv.wrapping_add(l.last_s);
        for i in 0..W760_A.len(){
            let w=lw*(W760_W[i]as u32); total=total.saturating_add(w);
            let mut st=pre; let mut q=[0u8;3];
            for j in 0..3usize{st=upd(st,la.wrapping_add(W760_A[i][j]),ls.wrapping_add(W760_S[i][j]));q[j]=st as u8}
            if q[0]>=0xc0{continue}
            let raw=((q[1]as u16)<<8)|q[2]as u16;
            if shiny(raw){
                shiny_weight=shiny_weight.saturating_add(w); shiny_mask|=1u8<<i;
                if w>best_contrib{best_contrib=w;best_raw=raw;best_idx=li;best_d=d}
            }
        }
        // Preserve each donor's measured primary deep profile as a small
        // independent hypothesis only when it is not already in the corpus list.
        if !w760_primary_is_listed(l.primary_a,l.primary_s){
            let w=lw*2; total=total.saturating_add(w);
            let mut st=pre; let mut q=[0u8;3];
            for j in 0..3usize{st=upd(st,la.wrapping_add(l.primary_a[j]),ls.wrapping_add(l.primary_s[j]));q[j]=st as u8}
            if q[0]<0xc0{
                let raw=((q[1]as u16)<<8)|q[2]as u16;
                if shiny(raw){shiny_weight=shiny_weight.saturating_add(w);if w>best_contrib{best_contrib=w;best_raw=raw;best_idx=li;best_d=d}}
            }
        }
    }
    if total==0 || shiny_weight==0 || best_contrib==0{return None}
    let score=((shiny_weight.saturating_mul(100)+total/2)/total).min(100)as u8;
    // Experimental first-pass gate: do not stop for a one-off weak tail.
    // The rel40 rebind remains authoritative after Exact2F.
    if score<12{return None}
    let l=&BUCKET_LANES[best_idx];
    let s40=apply_sums(state,l.p40_a[av as usize],l.p40_s[sv as usize]);
    let d40=((av.wrapping_add(l.o40a)as u16)<<8)|sv.wrapping_add(l.o40s)as u16;
    let s716=apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]);
    let d716=((av.wrapping_add(l.o716a)as u16)<<8)|sv.wrapping_add(l.o716s)as u16;
    let d717=((av.wrapping_add(l.o717a)as u16)<<8)|sv.wrapping_add(l.o717s)as u16;
    let s717=upd(s716,(d717>>8)as u8,d717 as u8);
    let pred=Prediction{lane_id:l.id,source:l.source,support_weight:score,shiny_mask,raw:best_raw,
        expected40_state:s40,expected40_div:d40,expected716_state:s716,expected716_div:d716,
        expected717_state:s717,expected717_div:d717};
    Some(BucketPrediction{prediction:pred,bucket,anchor:l.anchor,distance:best_d,radius:16,
        post_proto:l.post_proto,post_rot:l.post_rot})
}
'''
if 'pub fn evaluate_weighted_bucket' not in p:
    p += '\n'+weighted

new_monitor=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid { return; }
        let cur=rng_advance();
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
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);
        if let Some(bp)=practical::evaluate_weighted_bucket(bucket,reader.rng_state(),measured_div(),ai,si){
            self.bucket_model_active=true; self.bucket_anchor=bp.anchor; self.bucket_distance=bp.distance;
            self.bucket_radius=bp.radius; self.bucket_expected_post_proto=bp.post_proto; self.bucket_expected_post_rot=bp.post_rot;
            self.phase_target_proto=b'A'; self.phase_target_rot=10;
            self.practical_live_found_advance=cur; self.practical_live_found_state=reader.rng_state();
            self.practical_live_found_div=measured_div(); self.practical_live_found_tick=pnp::system_tick();
            self.practical_live_found_ai=ai; self.practical_live_found_si=si;
            self.bind_practical_prediction(bp.prediction);
            self.practical_live_found_lane=253; self.practical_empirical=false;
            self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);
            self.practical_live_scan=false; pre_vblank_timing_capture_stop(); pnp::request_pause();
        }
    }'''
t=replace_fn(t,'    fn live_root_monitor(&mut self, reader: &Gen2Reader)',new_monitor)

new_control=r'''    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {
        let mut out=0u32;
        if self.practical_live_found_lane==253 && self.practical_candidate_valid && !self.probe_session{out|=1u32<<31}
        let r=latest_pre_vblank_ring(); let count=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        let(proto,rot,best,second,consecutive)=classify_pre_ring(&r);
        self.phase_now_proto=proto; self.phase_now_rot=rot; self.phase_best_score=best;
        self.phase_second_score=second; self.phase_consecutive=consecutive;
        let cur=rng_advance();
        // v7.6.0 authoritative target: never silently migrate to another A/r10.
        if self.practical_live_found_lane==253 && self.practical_candidate_valid && !self.probe_session
            && cur>self.practical_target {
            self.practical_miss=8; out|=1u32<<26; return out;
        }
        if count==PRE_VBLANK_RING_LEN && consecutive && best==0{
            out|=1u32<<29; out|=proto as u32; out|=(rot as u32)<<8;
            let(_,p0)=pre_ring_sample(&r,0); let pd=p0.wrapping_sub(0x0035)&0x3fff;
            if (pd&0x003f)==0{
                let bucket=((pd>>6)&0xff)as u8; out|=1u32<<28; out|=(bucket as u32)<<12; self.bucket_current=bucket;
                if self.practical_live_found_lane==253 && self.practical_candidate_valid && !self.probe_session
                    && cur==self.practical_target && proto==b'A' && rot==10{
                    self.phase_target_proto=proto; self.phase_target_rot=rot;
                    self.practical_live_found_state=reader.rng_state(); self.practical_live_found_div=measured_div();
                    self.practical_live_found_tick=pnp::system_tick(); out|=1u32<<27;
                }
            }
        }
        out
    }'''
t=replace_fn(t,'    pub fn control_pause_cell(&mut self, reader: &Gen2Reader)',new_control)

# Replace benchmark scan display prefix with selector status.
start=t.index('        if self.practical_scan_enabled {',t.index('    pub fn draw_rng_status(&self)'))
end=t.index('        } else if self.practical_live_found_lane == 250',start)
newui='''        if self.practical_scan_enabled {\n            pnp::println!("S760 WEIGHTED SCAN");\n            pnp::println!("ADV{} ROOT{}",rng_advance(),self.practical_live_checked);\n            if self.phase_now_proto==b'?' {pnp::println!("PRE ?");} else {pnp::println!("PRE {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current);}\n            pnp::println!("Y+DOWN START / IDLE");\n'''
t=t[:start]+newui+t[end:]
# Update lane253 UI block conservatively.
old='''        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            if self.practical_candidate_valid && self.bucket_model_active {\n                pnp::println!("S738 SHINY LOCK");\n                pnp::println!("B{} A{} D{} R{}",self.bucket_current,self.bucket_anchor,self.bucket_distance,self.bucket_radius);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B ARM -> UP");\n            } else {\n                pnp::println!("S738 CONF SHINY SCAN");\n                if self.phase_now_proto==b'?' { pnp::println!("NOW ?"); }\n                else { pnp::println!("NOW {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current); }\n                pnp::println!("N{} R{}",self.bucket_scan_steps,self.bucket_radius);\n                pnp::println!("AUTO NEUTRAL - NO INPUT");\n            }\n'''
new='''        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            if self.practical_miss==8 {\n                pnp::println!("S760 TARGET MISSED");\n                pnp::println!("T{} NOW{}",self.practical_target,rng_advance());\n                pnp::println!("RESET VC");\n            } else if self.practical_candidate_valid && self.bucket_model_active {\n                pnp::println!("S760 WEIGHTED LOCK");\n                pnp::println!("SCORE {} T{}",self.practical_support,self.practical_target);\n                pnp::println!("B{} A{} D{}",self.bucket_current,self.bucket_anchor,self.bucket_distance);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");\n            } else {\n                pnp::println!("S760 LOCK WAIT");\n            }\n'''
if old not in t: raise SystemExit('lane253 UI anchor missing')
t=t.replace(old,new,1)
# Append selector telemetry before the normal trace close.
needle='''        pnp::trace_file_close();\n        set_vblank_context_capture(true);'''
ins='''        line.clear();\n        let _=write!(line,"\\nselector,version,target_advance,model_score,model_mask,bucket,anchor,distance,expected_post_proto,expected_post_rot,pred_raw,miss\\nSELECTOR760,V760,{},{},{:02X},{},{},{},{},{},{:04X},{}\\n",\n            self.practical_target,self.practical_support,self.practical_mask,self.bucket_current,self.bucket_anchor,self.bucket_distance,\n            if self.bucket_expected_post_proto==0{'?'}else{self.bucket_expected_post_proto as char},self.bucket_expected_post_rot,self.practical_raw,self.practical_miss);\n        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();\n        set_vblank_context_capture(true);'''
if needle not in t: raise SystemExit('save close anchor missing')
t=t.replace(needle,ins,1)

# Main: Y+DOWN only starts production selector. Restore left/right frame adjust;
# disable the old Y+UP sweep start.
m=m.replace('if (just_pressed & (KEY_DDOWN | KEY_DUP | KEY_DLEFT | KEY_DRIGHT))','if (just_pressed & KEY_DDOWN)',1)
oldslots='''                if (just_pressed & KEY_DDOWN) suicune_phase_slot = 12U; // IDLE\n                else if (just_pressed & KEY_DUP) suicune_phase_slot = 13U; // UP HOLD\n                else if (just_pressed & KEY_DLEFT) suicune_phase_slot = 14U; // B MASH\n                else suicune_phase_slot = 15U; // MENU IDLE'''
if oldslots not in m: raise SystemExit('slot block missing')
m=m.replace(oldslots,'                suicune_phase_slot = 8U; // v7.6 weighted selector',1)
# Disable the later legacy DDOWN/DUP scan branches; first DDOWN path already launches.
m=m.replace('            if (just_pressed & KEY_DDOWN)\n            {','            if (false && (just_pressed & KEY_DDOWN))\n            {',1)
m=m.replace('            if (just_pressed & KEY_DUP)\n            {','            if (false && (just_pressed & KEY_DUP))\n            {',1)
# Parse target-miss bit and stop root-lock stepping on overshoot.
anchor='''            bool shiny_ready = (cell & 0x08000000U) != 0;\n            suicune_root_lock_last_cell = cell;'''
if anchor not in m: raise SystemExit('main bit anchor missing')
m=m.replace(anchor,'''            bool shiny_ready = (cell & 0x08000000U) != 0;\n            bool target_miss = (cell & 0x04000000U) != 0;\n            suicune_root_lock_last_cell = cell;''',1)
anchor='''            if (suicune_root_lock_active && !suicune_root_lock_ready)\n            {\n                if (shiny_ready && valid && bucket_valid && proto == (u32)'A' && rot == 10U)'''
if anchor not in m: raise SystemExit('root block anchor missing')
m=m.replace(anchor,'''            if (suicune_root_lock_active && !suicune_root_lock_ready)\n            {\n                if (target_miss)\n                {\n                    suicune_root_lock_failed = true;\n                    suicune_root_lock_active = false;\n                    continue;\n                }\n                if (shiny_ready && valid && bucket_valid && proto == (u32)'A' && rot == 10U)''',1)

P.write_text(p)
T.write_text(t)
M.write_text(m)
print('Applied Suicune v7.6.0 Weighted Root Selector + authoritative target lock')
