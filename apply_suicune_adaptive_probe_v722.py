#!/usr/bin/env python3
from pathlib import Path

P=Path('reader_core/src/crystal/trace.rs')
s=P.read_text()

def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'v722 {label}: expected 1, got {n}')
    s=s.replace(old,new,1)

def fspan(text,sig):
    a=text.find(sig)
    if a<0: raise SystemExit('v722 function missing '+sig)
    b=text.find('{',a); d=0
    for i in range(b,len(text)):
        if text[i]=='{': d+=1
        elif text[i]=='}':
            d-=1
            if d==0:return a,i+1
    raise SystemExit('v722 unclosed '+sig)

# Extra diagnostics. Keep these in Trace only; no timing-sensitive hook changes.
rep('''    phase_target_count: u32,
    phase_target_proto: u8,''','''    phase_target_count: u32,
    phase_fallback_count: u32,
    phase_best_score: u16,
    phase_second_score: u16,
    phase_consecutive: bool,
    phase_target_proto: u8,''','fields')
rep('''            phase_target_count: 0,
            phase_target_proto: 0,''','''            phase_target_count: 0,
            phase_fallback_count: 0,
            phase_best_score: 0xffff,
            phase_second_score: 0xffff,
            phase_consecutive: false,
            phase_target_proto: 0,''','defaults')
rep('''        self.phase_target_count = 0;
        self.phase_target_proto = 0;''','''        self.phase_target_count = 0;
        self.phase_fallback_count = 0;
        self.phase_best_score = 0xffff;
        self.phase_second_score = 0xffff;
        self.phase_consecutive = false;
        self.phase_target_proto = 0;''','reset')

start,end=fspan(s,'    fn live_root_monitor(&mut self, reader: &Gen2Reader)')
monitor=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled
            || !self.practical_live_scan
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        { return; }

        let cur=rng_advance();
        if cur==self.practical_live_last_advance { return; }
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);

        // v7.2.2 deliberately inspects the raw 17-sample classifier so the UI
        // can explain why a root was not actionable.  This does not add any
        // hook-side reads; it uses the already-maintained PRE ring.
        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n!=PRE_VBLANK_RING_LEN {
            self.phase_now_proto=b'?'; self.phase_now_lag=0xff;
            self.practical_live_no_lane=self.practical_live_no_lane.saturating_add(1);
            return;
        }
        let(last,_)=pre_ring_sample(&r,n-1);
        let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best; self.phase_second_score=second; self.phase_consecutive=ok;
        if lag>1 || !ok {
            self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag.min(255) as u8;
            self.practical_live_no_lane=self.practical_live_no_lane.saturating_add(1);
            return;
        }
        if lag==1 { rot=rot.wrapping_add(1)&15; }
        self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag as u8;

        // Production-quality donor captures remain exact only.
        if lag!=0 || best!=0 { return; }
        if self.practical_live_checked < PRE_VBLANK_RING_LEN as u32 { return; }

        self.phase_exact_count=self.phase_exact_count.saturating_add(1);
        if let Some(ci)=Self::phase_cell_index(proto0,rot) {
            self.phase_counts[ci]=self.phase_counts[ci].saturating_add(1);
        }

        let priority=Self::phase_conflict_target(proto0,rot);
        if priority { self.phase_target_count=self.phase_target_count.saturating_add(1); }
        // Do not waste an entire run.  Before 3000 FR only the known conflict
        // cells are accepted; afterwards the first exact lag0 cell is a valid
        // fallback donor for phase/distribution analysis.
        let fallback=self.practical_live_checked>=3000;
        if !priority && !fallback { return; }
        if !priority { self.phase_fallback_count=self.phase_fallback_count.saturating_add(1); }

        let Some(ai0)=add_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1); return;
        };
        let Some(si0)=sub_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1); return;
        };
        let ai=(ai0 as u32)&0x3fff; let si=(si0 as u32)&0x3fff;
        self.practical_live_lane_frames=self.practical_live_lane_frames.saturating_add(1);
        self.phase_target_proto=proto0; self.phase_target_rot=rot;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=252;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai; self.practical_live_found_si=si;
        self.practical_live_scan=false; self.practical_scan_enabled=false;
        pre_vblank_timing_capture_stop();
        self.practical_candidate_valid=false; self.practical_active=false;
        pnp::request_pause();
    }'''
s=s[:start]+monitor+s[end:]

# Extend PHASESCAN with fallback and classifier diagnostics.
rep('''"phase_scan,version,start,found,fr,exact,target_hits,target_proto,target_rot,last_proto,last_rot,last_lag,no_class,index_wait\\nPHASESCAN,V721,{},{},{},{},{},{},{},{},{},{},{},{}\\n",''','''"phase_scan,version,start,found,fr,exact,target_hits,fallback_hits,target_proto,target_rot,last_proto,last_rot,last_lag,best,second,consecutive,no_class,index_wait\\nPHASESCAN,V722,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n",''','csv header')
rep('''                self.phase_target_count,
                self.phase_target_proto as char,''','''                self.phase_target_count,
                self.phase_fallback_count,
                self.phase_target_proto as char,''','csv fallback')
rep('''                self.phase_now_lag,
                self.practical_live_no_lane,
                self.practical_live_index_wait''','''                self.phase_now_lag,
                self.phase_best_score,
                self.phase_second_score,
                self.phase_consecutive as u8,
                self.practical_live_no_lane,
                self.practical_live_index_wait''','csv diagnostics')
s=s.replace('PRECOUNT,V721','PRECOUNT,V722')

old='''        if self.practical_scan_enabled {
            pnp::println!("S721 MULTI PHASE");
            if self.phase_now_proto == b'?' {
                pnp::println!("NOW ?");
            } else {
                pnp::println!("NOW {}/r{} L{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag);
            }
            pnp::println!("FR{} EX{}", self.practical_live_checked, self.phase_exact_count);
            if self.practical_live_checked >= 10000 {
                pnp::println!("RESET SUGGESTED");
            } else {
                pnp::println!("TGT A3 A10 B1 B11 D12");
            }
        } else if self.practical_live_found_lane == 251 && !self.probe_session {
            pnp::println!("S721 PROBE {}/r{}", self.phase_target_proto as char, self.phase_target_rot);
            pnp::println!("UP+B DONOR");
'''
new='''        if self.practical_scan_enabled {
            pnp::println!("S722 ADAPTIVE PHASE");
            if self.phase_now_proto == b'?' { pnp::println!("NOW ?"); }
            else { pnp::println!("NOW {}/r{} L{} S{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag, self.phase_best_score); }
            pnp::println!("FR{} EX{} TG{} IW{}", self.practical_live_checked, self.phase_exact_count, self.phase_target_count, self.practical_live_index_wait);
            if self.practical_live_checked < 3000 { pnp::println!("PRI A3 A10 B1 B11 D12"); }
            else { pnp::println!("FALLBACK ANY EXACT"); }
        } else if self.practical_live_found_lane == 252 && !self.probe_session {
            pnp::println!("S722 PROBE {}/r{}", self.phase_target_proto as char, self.phase_target_rot);
            pnp::println!("UP+B DONOR");
'''
rep(old,new,'ui')
s=s.replace('S721 PHASE RUN','S722 PHASE RUN').replace('S721 IDLE','S722 IDLE')
P.write_text(s)
print('Applied v7.2.2 Adaptive Phase Probe: transparent diagnostics + 3000FR any-exact fallback')
