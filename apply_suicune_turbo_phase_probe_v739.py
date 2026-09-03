#!/usr/bin/env python3
from pathlib import Path

p=Path('reader_core/src/crystal/trace.rs')
ts=p.read_text()

# Dedicated diagnostic state. This build never auto-arms a Suicune encounter.
old='''    bucket_expected_post_proto: u8,\n    bucket_expected_post_rot: u8,\n    phase_now_proto: u8,'''
new='''    bucket_expected_post_proto: u8,\n    bucket_expected_post_rot: u8,\n    turbo_a10_count: u16,\n    turbo_match_count: u16,\n    turbo_mismatch_count: u16,\n    turbo_last_advance: u32,\n    turbo_last_bucket: u8,\n    turbo_last_da: u32,\n    turbo_last_db: u8,\n    turbo_first_bad_index: u16,\n    turbo_first_bad_da: u32,\n    turbo_first_bad_db: u8,\n    turbo_freeze_delta: u32,\n    phase_now_proto: u8,'''
assert old in ts
ts=ts.replace(old,new,1)

old='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            phase_now_proto: b'?', '''
if old not in ts:
    old='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            phase_now_proto: b'?',\n'''
    new='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            turbo_a10_count: 0,\n            turbo_match_count: 0,\n            turbo_mismatch_count: 0,\n            turbo_last_advance: 0,\n            turbo_last_bucket: 0,\n            turbo_last_da: 0,\n            turbo_last_db: 0,\n            turbo_first_bad_index: 0,\n            turbo_first_bad_da: 0,\n            turbo_first_bad_db: 0,\n            turbo_freeze_delta: 0,\n            phase_now_proto: b'?',\n'''
else:
    new='''            bucket_expected_post_proto: 0,\n            bucket_expected_post_rot: 0,\n            turbo_a10_count: 0,\n            turbo_match_count: 0,\n            turbo_mismatch_count: 0,\n            turbo_last_advance: 0,\n            turbo_last_bucket: 0,\n            turbo_last_da: 0,\n            turbo_last_db: 0,\n            turbo_first_bad_index: 0,\n            turbo_first_bad_da: 0,\n            turbo_first_bad_db: 0,\n            turbo_freeze_delta: 0,\n            phase_now_proto: b'?', '''
assert old in ts
ts=ts.replace(old,new,1)

old='''        self.bucket_expected_post_proto = 0;\n        self.bucket_expected_post_rot = 0;\n        self.phase_now_proto = b'?';'''
new='''        self.bucket_expected_post_proto = 0;\n        self.bucket_expected_post_rot = 0;\n        self.turbo_a10_count = 0;\n        self.turbo_match_count = 0;\n        self.turbo_mismatch_count = 0;\n        self.turbo_last_advance = 0;\n        self.turbo_last_bucket = 0;\n        self.turbo_last_da = 0;\n        self.turbo_last_db = 0;\n        self.turbo_first_bad_index = 0;\n        self.turbo_first_bad_da = 0;\n        self.turbo_first_bad_db = 0;\n        self.turbo_freeze_delta = 0;\n        self.phase_now_proto = b'?';'''
assert old in ts
ts=ts.replace(old,new,1)

# Replace production live-root entry with a free-running A/r10 recurrence probe.
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

        // Keep the existing epoch guard: a non-A exact cell means this boot is
        // unsuitable for the A/r10 phase experiment.
        if proto0!=b'A' {
            self.phase_target_proto=proto0; self.phase_target_rot=rot;
            self.practical_live_found_advance=cur;
            self.practical_live_found_state=reader.rng_state();
            self.practical_live_found_div=measured_div();
            self.practical_live_found_lane=254;
            self.practical_live_found_tick=pnp::system_tick();
            self.practical_live_scan=false; self.practical_scan_enabled=false;
            pnp::request_pause(); return;
        }

        // v7.3.9: unlike v7.3.8, do NOT pause on the first A cell. Let the VC
        // free-run and sample only exact A/r10 roots. This directly tests the
        // hardware recurrence hypothesis: +16 advances and +37 bucket.
        if rot!=10 { return; }
        let(_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0 { return; }
        let bucket=((pd>>6)&0xff)as u8;
        self.bucket_current=bucket;
        self.phase_target_count=self.phase_target_count.saturating_add(1);

        if self.turbo_a10_count!=0 {
            let da=cur.wrapping_sub(self.turbo_last_advance);
            let db=bucket.wrapping_sub(self.turbo_last_bucket);
            self.turbo_last_da=da;
            self.turbo_last_db=db;
            if da==16 && db==37 {
                self.turbo_match_count=self.turbo_match_count.saturating_add(1);
            } else {
                self.turbo_mismatch_count=self.turbo_mismatch_count.saturating_add(1);
                if self.turbo_first_bad_index==0 {
                    self.turbo_first_bad_index=self.turbo_a10_count;
                    self.turbo_first_bad_da=da;
                    self.turbo_first_bad_db=db;
                }
            }
        }
        self.turbo_last_advance=cur;
        self.turbo_last_bucket=bucket;
        self.turbo_a10_count=self.turbo_a10_count.saturating_add(1);

        if self.turbo_a10_count>=64 {
            self.practical_live_found_advance=cur;
            self.practical_live_found_state=reader.rng_state();
            self.practical_live_found_div=measured_div();
            self.practical_live_found_lane=252; // TURBO PROBE DONE, never encounter-arm
            self.practical_live_found_tick=pnp::system_tick();
            self.practical_live_scan=false; self.practical_scan_enabled=false;
            pnp::request_pause();
        }
    }
'''
ts=ts[:start]+newfn+ts[end:]

# Measure how far the free-running root moved before the bottom-screen pause loop
# actually became authoritative.
needle='''        let cur=rng_advance();\n        if cur!=self.bucket_control_last_advance {'''
repl='''        let cur=rng_advance();\n        if self.practical_live_found_lane==252 {\n            self.turbo_freeze_delta=cur.wrapping_sub(self.practical_live_found_advance);\n        }\n        if cur!=self.bucket_control_last_advance {'''
assert needle in ts
ts=ts.replace(needle,repl,1)

# Dedicated overlay. The probe is deliberately non-production: no B/UP arm path
# is exposed when lane252 is reached.
start=ts.index('    pub fn draw_rng_status(&self) {')
seg=ts[start:]
old='''        if self.practical_scan_enabled {\n            pnp::println!("S738 A-EPOCH SCAN");\n            if self.phase_now_proto == b'?' { pnp::println!("NOW ?"); }\n            else { pnp::println!("NOW {}/r{} L{} S{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag, self.phase_best_score); }\n            pnp::println!("FR{} EX{}", self.practical_live_checked, self.phase_exact_count);\n            pnp::println!("A EPOCH -> PAUSE SEARCH");\n        } else if self.practical_live_found_lane == 254 && !self.probe_session {'''
new='''        if self.practical_scan_enabled {\n            pnp::println!("S739 TURBO PHASE");\n            pnp::println!("A10 {}/64 OK{} BAD{}",self.turbo_a10_count,self.turbo_match_count,self.turbo_mismatch_count);\n            pnp::println!("LAST dA{} dB{}",self.turbo_last_da,self.turbo_last_db);\n            pnp::println!("FREE RUN - NO INPUT");\n        } else if self.practical_live_found_lane == 252 && !self.probe_session {\n            pnp::println!("S739 TURBO DONE");\n            pnp::println!("A10 {} OK{} BAD{}",self.turbo_a10_count,self.turbo_match_count,self.turbo_mismatch_count);\n            pnp::println!("LAST dA{} dB{} FZ+{}",self.turbo_last_da,self.turbo_last_db,self.turbo_freeze_delta);\n            pnp::println!("BAD#{} dA{} dB{}",self.turbo_first_bad_index,self.turbo_first_bad_da,self.turbo_first_bad_db);\n        } else if self.practical_live_found_lane == 254 && !self.probe_session {'''
assert old in seg
seg=seg.replace(old,new,1)
seg=seg.replace('S732 NEED A EPOCH','S739 NEED A EPOCH',1)
ts=ts[:start]+seg

p.write_text(ts)
print('Applied v7.3.9 Turbo Phase Probe: 64 free-running A/r10 samples, +16/+37 recurrence and freeze-delta diagnostics')
