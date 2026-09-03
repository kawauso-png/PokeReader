#!/usr/bin/env python3
from pathlib import Path

p=Path('reader_core/src/crystal/trace.rs')
t=Path('3gx/sources/main.c')
ts=p.read_text(); ms=t.read_text()

# Diagnostics for the production turbo handoff. Live scan only requests the
# pause; the frozen root is re-evaluated before SHINY LOCK is exposed.
old='''    bucket_expected_post_proto: u8,\n    bucket_expected_post_rot: u8,\n    phase_now_proto: u8,'''
new='''    bucket_expected_post_proto: u8,\n    bucket_expected_post_rot: u8,\n    turbo_candidate_advance: u32,\n    turbo_freeze_delta: u32,\n    turbo_recheck_count: u32,\n    turbo_recheck_miss: u32,\n    phase_now_proto: u8,'''
assert old in ts
ts=ts.replace(old,new,1)

old='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            phase_now_proto: b'?',\n'''
new='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            turbo_candidate_advance: 0,\n            turbo_freeze_delta: u32::MAX,\n            turbo_recheck_count: 0,\n            turbo_recheck_miss: 0,\n            phase_now_proto: b'?',\n'''
assert old in ts
ts=ts.replace(old,new,1)

old='''        self.bucket_expected_post_proto = 0;\n        self.bucket_expected_post_rot = 0;\n        self.phase_now_proto = b'?';'''
new='''        self.bucket_expected_post_proto = 0;\n        self.bucket_expected_post_rot = 0;\n        self.turbo_candidate_advance = 0;\n        self.turbo_freeze_delta = u32::MAX;\n        self.turbo_recheck_count = 0;\n        self.turbo_recheck_miss = 0;\n        self.phase_now_proto = b'?';'''
assert old in ts
ts=ts.replace(old,new,1)

# Free-running production scan. Only exact A/r10 roots are expensive-evaluated.
# v739 hardware: 62/63 one-step recurrences were +16/+37; the only miss was
# exactly +32/+74 (one observation skipped), and request_pause froze at FZ+0.
# We do NOT rely on FZ+0 for correctness: the pause-side root is always rechecked.
start=ts.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
end=ts.index('\n    fn practical_fail',start)
newfn=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid { return; }
        let cur=rng_advance();
        if cur==self.practical_live_last_advance { return; }
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);
        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n!=PRE_VBLANK_RING_LEN { self.phase_now_proto=b'?'; self.phase_now_lag=0xff; return; }
        let(last,_)=pre_ring_sample(&r,n-1);
        let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best; self.phase_second_score=second; self.phase_consecutive=ok;
        if lag>1||!ok { self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag.min(255)as u8; return; }
        if lag==1 { rot=rot.wrapping_add(1)&15; }
        self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag as u8;
        if lag!=0||best!=0 { return; }
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);

        // Preserve the established epoch gate. A non-A exact prototype means
        // this boot is not the A/r10 epoch used by the measured bucket donors.
        if proto0!=b'A' {
            self.phase_target_proto=proto0; self.phase_target_rot=rot;
            self.practical_live_found_advance=cur;
            self.practical_live_found_state=reader.rng_state();
            self.practical_live_found_div=measured_div();
            self.practical_live_found_lane=254;
            self.practical_live_found_tick=pnp::system_tick();
            self.practical_live_found_ai=0; self.practical_live_found_si=0;
            self.practical_live_scan=false; self.practical_scan_enabled=false;
            self.practical_candidate_valid=false; self.practical_active=false;
            pnp::request_pause(); return;
        }

        // v7.4.0 turbo path: let the VC run normally and inspect only exact
        // A/r10 roots. No game pause occurs for non-candidates.
        if rot!=10 { return; }
        self.phase_target_count=self.phase_target_count.saturating_add(1);
        let(_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0 { return; }
        let bucket=((pd>>6)&0xff)as u8;
        self.bucket_current=bucket;

        let (Some(ai),Some(si))=(add_div_tracker().index(),sub_div_tracker().index()) else { return; };
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);

        // Use the final v738 confidence envelope immediately (R16). The
        // evaluator itself still enforces tracker safety, distance-dependent
        // support, primary/global dedup, and rejects distance >16.
        let Some(bp)=practical::evaluate_adaptive_bucket(
            bucket,reader.rng_state(),measured_div(),ai as u32,si as u32,6144
        ) else { return; };

        // This is only a live candidate. Deliberately DO NOT call
        // bind_practical_prediction here; candidate_valid remains false until
        // control_pause_cell() re-evaluates the authoritative frozen root.
        self.bucket_anchor=bp.anchor;
        self.bucket_distance=bp.distance;
        self.bucket_radius=16;
        self.bucket_expected_post_proto=bp.post_proto;
        self.bucket_expected_post_rot=bp.post_rot;
        self.turbo_candidate_advance=cur;
        self.turbo_freeze_delta=u32::MAX;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=253;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai as u32;
        self.practical_live_found_si=si as u32;
        self.practical_live_scan=false;
        self.practical_scan_enabled=false;
        self.practical_candidate_valid=false;
        self.practical_active=false;

        // Keep the pause-side confidence envelope at R16 immediately. If the
        // pause transport ever lands on a different root, the existing neutral
        // root-lock becomes a safe fallback rather than accepting the stale
        // live prediction.
        self.bucket_scan_steps=6144;
        self.bucket_control_last_advance=u32::MAX;
        pnp::request_pause();
    }
'''
ts=ts[:start]+newfn+ts[end:]

# Pause-side diagnostics and authoritative recheck accounting.
needle='''        let cur=rng_advance();\n        if cur!=self.bucket_control_last_advance {'''
repl='''        let cur=rng_advance();\n        if self.practical_live_found_lane==253 && self.turbo_candidate_advance!=0\n            && self.turbo_freeze_delta==u32::MAX {\n            self.turbo_freeze_delta=cur.wrapping_sub(self.turbo_candidate_advance);\n        }\n        if cur!=self.bucket_control_last_advance {'''
assert needle in ts
ts=ts.replace(needle,repl,1)

needle='''                if proto==b'A' && rot==10 && self.practical_live_found_lane==253 && !self.probe_session {\n                    self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);\n                    if let Some(bp)=practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_div_tracker().index().unwrap_or(0) as u32,sub_div_tracker().index().unwrap_or(0) as u32,self.bucket_scan_steps) {'''
repl='''                if proto==b'A' && rot==10 && self.practical_live_found_lane==253 && !self.probe_session {\n                    self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);\n                    self.turbo_recheck_count=self.turbo_recheck_count.saturating_add(1);\n                    if let Some(bp)=practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_div_tracker().index().unwrap_or(0) as u32,sub_div_tracker().index().unwrap_or(0) as u32,self.bucket_scan_steps) {'''
assert needle in ts
ts=ts.replace(needle,repl,1)

needle='''                        self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);\n                        out|=1u32<<27;\n                    }\n                }'''
repl='''                        self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);\n                        out|=1u32<<27;\n                    } else {\n                        self.turbo_recheck_miss=self.turbo_recheck_miss.saturating_add(1);\n                    }\n                }'''
assert needle in ts
ts=ts.replace(needle,repl,1)

# UI: production turbo scan / authoritative frozen lock.
ts=ts.replace('pnp::println!("S738 A-EPOCH SCAN");','pnp::println!("S740 TURBO SHINY");',1)
ts=ts.replace('pnp::println!("A EPOCH -> PAUSE SEARCH");','pnp::println!("A10 LIVE - NO INPUT");',1)
ts=ts.replace('pnp::println!("S738 SHINY LOCK");','pnp::println!("S740 SHINY LOCK");',1)
old='''                pnp::println!("B{} A{} D{} R{}",self.bucket_current,self.bucket_anchor,self.bucket_distance,self.bucket_radius);\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);'''
new='''                pnp::println!("B{} A{} D{} FZ+{}",self.bucket_current,self.bucket_anchor,self.bucket_distance,if self.turbo_freeze_delta==u32::MAX{9999}else{self.turbo_freeze_delta});\n                pnp::println!("P{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);'''
assert old in ts
ts=ts.replace(old,new,1)
old='''                pnp::println!("S738 CONF SHINY SCAN");\n                if self.phase_now_proto==b'?' { pnp::println!("NOW ?"); }\n                else { pnp::println!("NOW {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current); }\n                pnp::println!("N{} R{}",self.bucket_scan_steps,self.bucket_radius);\n                pnp::println!("AUTO NEUTRAL - NO INPUT");'''
new='''                pnp::println!("S740 TURBO RECHECK");\n                if self.phase_now_proto==b'?' { pnp::println!("NOW ?"); }\n                else { pnp::println!("NOW {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current); }\n                pnp::println!("FZ+{} RC{} M{}",if self.turbo_freeze_delta==u32::MAX{9999}else{self.turbo_freeze_delta},self.turbo_recheck_count,self.turbo_recheck_miss);\n                pnp::println!("SAFE NEUTRAL FALLBACK");'''
assert old in ts
ts=ts.replace(old,new,1)
ts=ts.replace('S732 NEED A EPOCH','S740 NEED A EPOCH',1)

# Add turbo transport diagnostics to the saved encounter CSV.
old='''        line.clear();\n        let _ = write!(line,\n            "\\nadaptive_bucket,version,bucket,anchor,distance,radius,steps,expected_post_proto,expected_post_rot,actual_post_proto,actual_post_rot,wanted_slot,pred_raw,pred_mask,pred_lane,pred_source\\nBUCKET738,V738,{},{},{},{},{},{},{},{},{},1,{:04X},{:02X},{},{}\\n",'''
new='''        line.clear();\n        let _ = write!(line,\n            "\\nturbo,version,candidate_advance,freeze_delta,recheck_count,recheck_miss\\nTURBO,V740,{},{},{},{}\\n\\nadaptive_bucket,version,bucket,anchor,distance,radius,steps,expected_post_proto,expected_post_rot,actual_post_proto,actual_post_rot,wanted_slot,pred_raw,pred_mask,pred_lane,pred_source\\nBUCKET740,V740,{},{},{},{},{},{},{},{},{},1,{:04X},{:02X},{},{}\\n",\n            self.turbo_candidate_advance,if self.turbo_freeze_delta==u32::MAX{0xffffffff}else{self.turbo_freeze_delta},self.turbo_recheck_count,self.turbo_recheck_miss,'''
assert old in ts
ts=ts.replace(old,new,1)

# C host behavior is intentionally unchanged: lane253 is a pause-root request
# and shiny_ready from the frozen Rust recheck is still mandatory before B->UP.
ms=ms.replace('// v7.3.2 authoritative frozen-root lock.', '// v7.4.0 turbo handoff + authoritative frozen-root lock.',1)

p.write_text(ts); t.write_text(ms)
print('Applied v7.4.0 Turbo Shiny: free-running A/r10 evaluation, frozen-root recheck, safe neutral fallback')
