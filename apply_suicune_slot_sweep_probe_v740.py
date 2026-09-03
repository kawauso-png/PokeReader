#!/usr/bin/env python3
from pathlib import Path
P=Path('reader_core/src/crystal/trace.rs'); M=Path('3gx/sources/main.c')
t=P.read_text(); m=M.read_text()

def rep(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'{label}: {n}')
    return s.replace(a,b,1)

old='''    turbo_freeze_delta: u32,\n    phase_now_proto: u8,'''
new='''    turbo_freeze_delta: u32,\n    sweep_target_bucket: u8,\n    sweep_freeze_delta: u32,\n    sweep_a10_seen: u32,\n    phase_now_proto: u8,'''
t=rep(t,old,new,'fields')
old='''            turbo_freeze_delta: 0,\n            phase_now_proto: b'?','''
new='''            turbo_freeze_delta: 0,\n            sweep_target_bucket: 76,\n            sweep_freeze_delta: 0,\n            sweep_a10_seen: 0,\n            phase_now_proto: b'?','''
t=rep(t,old,new,'default fields')
old='''        self.turbo_freeze_delta = 0;\n        self.phase_now_proto = b'?';'''
new='''        self.turbo_freeze_delta = 0;\n        self.sweep_target_bucket = match pnp::fixed_a_frame().phase_slot { 9 => 39, _ => 76 };\n        self.sweep_freeze_delta = 0;\n        self.sweep_a10_seen = 0;\n        self.phase_now_proto = b'?';'''
t=rep(t,old,new,'reset scan')

start=t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
end=t.index('\n    fn practical_fail',start)
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

        if proto0!=b'A' {
            self.phase_target_proto=proto0; self.phase_target_rot=rot;
            self.practical_live_found_advance=cur;
            self.practical_live_found_state=reader.rng_state();
            self.practical_live_found_div=measured_div();
            self.practical_live_found_lane=254;
            self.practical_live_found_tick=pnp::system_tick();
            self.practical_live_scan=false; self.practical_scan_enabled=false;
            pre_vblank_timing_capture_stop();
            pnp::request_pause(); return;
        }
        if rot!=10 { return; }
        let(_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0 { return; }
        let bucket=((pd>>6)&0xff)as u8;
        self.bucket_current=bucket;
        self.sweep_a10_seen=self.sweep_a10_seen.saturating_add(1);
        self.phase_target_count=self.phase_target_count.saturating_add(1);
        if bucket!=self.sweep_target_bucket { return; }

        self.phase_target_proto=proto0; self.phase_target_rot=rot;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=251;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=add_div_tracker().index().unwrap_or(0) as u32;
        self.practical_live_found_si=sub_div_tracker().index().unwrap_or(0) as u32;
        self.practical_live_scan=false; self.practical_scan_enabled=false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }
'''
t=t[:start]+newfn+t[end:]

old='''        if self.practical_live_found_lane==253 && !self.probe_session { out|=1u32<<31; }'''
new='''        if (self.practical_live_found_lane==253 || self.practical_live_found_lane==251) && !self.probe_session { out|=1u32<<31; }'''
t=rep(t,old,new,'requested sentinel')
old='''        if self.practical_live_found_lane==252 {\n            self.turbo_freeze_delta=cur.wrapping_sub(self.practical_live_found_advance);\n        }'''
new='''        if self.practical_live_found_lane==252 {\n            self.turbo_freeze_delta=cur.wrapping_sub(self.practical_live_found_advance);\n        }\n        if self.practical_live_found_lane==251 {\n            self.sweep_freeze_delta=cur.wrapping_sub(self.practical_live_found_advance);\n        }'''
t=rep(t,old,new,'freeze delta')
needle='''                self.bucket_current=bucket;\n                if proto==b'A' && rot==10 && self.practical_live_found_lane==253 && !self.probe_session {'''
repl='''                self.bucket_current=bucket;\n                if proto==b'A' && rot==10 && self.practical_live_found_lane==251 && !self.probe_session\n                    && bucket==self.sweep_target_bucket {\n                    self.phase_target_proto=proto; self.phase_target_rot=rot;\n                    self.practical_live_found_advance=cur;\n                    self.practical_live_found_state=reader.rng_state();\n                    self.practical_live_found_div=measured_div();\n                    self.practical_live_found_tick=pnp::system_tick();\n                    self.practical_live_found_ai=add_div_tracker().index().unwrap_or(0) as u32;\n                    self.practical_live_found_si=sub_div_tracker().index().unwrap_or(0) as u32;\n                    out|=1u32<<27;\n                }\n                if proto==b'A' && rot==10 && self.practical_live_found_lane==253 && !self.probe_session {'''
t=rep(t,needle,repl,'sweep ready')

start=t.index('    pub fn draw_rng_status(&self) {')
seg=t[start:]
old='''        if self.practical_scan_enabled {\n            pnp::println!("S739 TURBO PHASE");\n            pnp::println!("A10 {}/64 OK{} BAD{}",self.turbo_a10_count,self.turbo_match_count,self.turbo_mismatch_count);\n            pnp::println!("LAST dA{} dB{}",self.turbo_last_da,self.turbo_last_db);\n            pnp::println!("FREE RUN - NO INPUT");\n        } else if self.practical_live_found_lane == 252 && !self.probe_session {\n            pnp::println!("S739 TURBO DONE");\n            pnp::println!("A10 {} OK{} BAD{}",self.turbo_a10_count,self.turbo_match_count,self.turbo_mismatch_count);\n            pnp::println!("LAST dA{} dB{} FZ+{}",self.turbo_last_da,self.turbo_last_db,self.turbo_freeze_delta);\n            pnp::println!("BAD#{} dA{} dB{}",self.turbo_first_bad_index,self.turbo_first_bad_da,self.turbo_first_bad_db);\n        } else if self.practical_live_found_lane == 254 && !self.probe_session {'''
new='''        if self.practical_scan_enabled {\n            pnp::println!("S740 B{} TURBO",self.sweep_target_bucket);\n            pnp::println!("NOW {}/r{} B{}",self.phase_now_proto as char,self.phase_now_rot,self.bucket_current);\n            pnp::println!("A10 {} FR{}",self.sweep_a10_seen,self.practical_live_checked);\n            pnp::println!("FREE RUN - NO INPUT");\n        } else if self.practical_live_found_lane == 251 && !self.probe_session {\n            pnp::println!("S740 B{} SWEEP FOUND",self.sweep_target_bucket);\n            pnp::println!("A/r10 TARGET; WAIT 0.5s");\n            pnp::println!("SLOT0 BASE  X=+1");\n            pnp::println!("THEN B -> RELEASE -> UP");\n        } else if self.practical_live_found_lane == 254 && !self.probe_session {'''
if old not in seg: raise SystemExit('UI old missing')
seg=seg.replace(old,new,1).replace('S739 NEED A EPOCH','S740 NEED A EPOCH',1)
t=t[:start]+seg

anchor='''        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();'''
row='''        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let actual_raw=self.probe_result.map(|x|x.raw_dv).unwrap_or(0);\n        let actual_route=self.probe_result.map(|x|x.route).unwrap_or(0);\n        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_slot,actual_slot,post_proto,post_rot,raw_dv,route,freeze_delta\\nSWEEP,V740,{},{},{},{},{},{},{:04X},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&7,\n            if rpm.period!=0{((rpm.actual/rpm.period)&7)as u32}else{255},\n            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,\n            actual_raw,actual_route,self.sweep_freeze_delta);\n        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();'''
t=rep(t,anchor,row,'sweep csv')

old='''            if (just_pressed & KEY_DDOWN)\n            {\n                suicune_root_lock_active = false;\n                suicune_root_lock_ready = false;\n                suicune_root_lock_failed = false;\n                suicune_wait_up_after_b = false;\n                suicune_root_lock_steps = 0;\n                suicune_root_lock_last_cell = 0;\n                suicune_phase_slot = 1;\n                search_suicune_practical_targets();\n                svcSleepThread(1000000);\n                continue;\n            }'''
new='''            if (just_pressed & KEY_DDOWN)\n            {\n                suicune_root_lock_active = false;\n                suicune_root_lock_ready = false;\n                suicune_root_lock_failed = false;\n                suicune_wait_up_after_b = false;\n                suicune_root_lock_steps = 0;\n                suicune_root_lock_last_cell = 0;\n                suicune_phase_slot = 8;\n                search_suicune_practical_targets();\n                svcSleepThread(1000000);\n                continue;\n            }\n            if (just_pressed & KEY_DUP)\n            {\n                suicune_root_lock_active = false;\n                suicune_root_lock_ready = false;\n                suicune_root_lock_failed = false;\n                suicune_wait_up_after_b = false;\n                suicune_root_lock_steps = 0;\n                suicune_root_lock_last_cell = 0;\n                suicune_phase_slot = 9;\n                search_suicune_practical_targets();\n                svcSleepThread(1000000);\n                continue;\n            }'''
m=rep(m,old,new,'scan selectors')

old='''                    suicune_root_lock_ready = true;\n                    suicune_root_lock_active = false;\n                    continue;'''
new='''                    suicune_root_lock_ready = true;\n                    suicune_root_lock_active = false;\n                    if (suicune_phase_slot >= 8U) suicune_phase_slot = 0U;\n                    continue;'''
m=rep(m,old,new,'ready slot0')

old='''            suicune_phase_slot = 1;\n            continue;'''
new='''            suicune_phase_slot = (suicune_phase_slot + 1U) & 7U;\n            continue;'''
pos=m.index('// v7.3 A/r10 control selector. X is consumed inside the pause loop;')
sub=m[pos:]
if old not in sub: raise SystemExit('x selector body missing')
sub=sub.replace(old,new,1)
m=m[:pos]+sub
m=m.replace('// v7.3 A/r10 control selector. X is consumed inside the pause loop;','// v7.4.0 slot-sweep selector. X is consumed inside the pause loop;')
m=m.replace('// no VC frame is released.  Only the two experimentally supported\n        // A/r10 slots are exposed in this causal validation build.','// no VC frame is released. Cycle absolute SLOT0..7 while frozen.')

P.write_text(t);M.write_text(m)
print('Applied v7.4.0 Slot Sweep Probe: B76/B39 turbo targets and SLOT0..7 absolute resume sweep')
