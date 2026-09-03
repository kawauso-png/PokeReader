#!/usr/bin/env python3
from pathlib import Path

T=Path('reader_core/src/crystal/trace.rs')
M=Path('3gx/sources/main.c')
t=T.read_text(); m=M.read_text()

def need(x,msg):
    if not x: raise SystemExit('v744 '+msg)

def rep(src,old,new,msg):
    n=src.count(old)
    if n!=1: raise SystemExit(f'v744 {msg}: expected 1 got {n}')
    return src.replace(old,new,1)

# -------------------------------------------------------------------------
# v7.4.4 Legal Advance Speed Benchmark
# - No RNG/DIV/state/DV writes.
# - No HID injection: all measured inputs are physical, ordinary game inputs.
# - 2 s warmup followed by 10 s measurement.
# - Measures actual RNG advance/sec plus A/r10/sec under the same PRE classifier.
# - Auto-saves one BENCH CSV and pauses after the measurement window.
# -------------------------------------------------------------------------

# Dedicated benchmark fields. Keep the old sweep fields intact so the patch
# remains isolated from the validated v742 timing/trace machinery.
old='''    sweep_a10_seen: u32,\n    phase_now_proto: u8,'''
new='''    sweep_a10_seen: u32,\n    bench_tag: u8,\n    bench_phase: u8,\n    bench_boot_tick: u64,\n    bench_start_tick: u64,\n    bench_elapsed_ticks: u64,\n    bench_start_advance: u32,\n    bench_adv_delta: u32,\n    bench_advance_events: u32,\n    bench_max_jump: u32,\n    bench_frame_samples: u32,\n    bench_exact_cells: u32,\n    bench_a10_count: u32,\n    bench_bucket_intervals: u32,\n    bench_bucket_ok: u32,\n    bench_bucket_bad: u32,\n    bench_last_a10_advance: u32,\n    bench_last_bucket: u8,\n    bench_last_bucket_valid: bool,\n    bench_last_keys: u32,\n    bench_keys_or: u32,\n    bench_key_changes: u32,\n    bench_up_samples: u32,\n    bench_b_samples: u32,\n    bench_start_samples: u32,\n    bench_start_state: u16,\n    bench_start_div: u16,\n    bench_end_state: u16,\n    bench_end_div: u16,\n    phase_now_proto: u8,'''
t=rep(t,old,new,'fields')

old='''            sweep_a10_seen: 0,\n            phase_now_proto: b'?', '''
if old not in t:
    old='''            sweep_a10_seen: 0,\n            phase_now_proto: b'?',\n'''
    new='''            sweep_a10_seen: 0,\n            bench_tag: 0,\n            bench_phase: 0,\n            bench_boot_tick: 0,\n            bench_start_tick: 0,\n            bench_elapsed_ticks: 0,\n            bench_start_advance: 0,\n            bench_adv_delta: 0,\n            bench_advance_events: 0,\n            bench_max_jump: 0,\n            bench_frame_samples: 0,\n            bench_exact_cells: 0,\n            bench_a10_count: 0,\n            bench_bucket_intervals: 0,\n            bench_bucket_ok: 0,\n            bench_bucket_bad: 0,\n            bench_last_a10_advance: 0,\n            bench_last_bucket: 0,\n            bench_last_bucket_valid: false,\n            bench_last_keys: 0,\n            bench_keys_or: 0,\n            bench_key_changes: 0,\n            bench_up_samples: 0,\n            bench_b_samples: 0,\n            bench_start_samples: 0,\n            bench_start_state: 0,\n            bench_start_div: 0,\n            bench_end_state: 0,\n            bench_end_div: 0,\n            phase_now_proto: b'?',\n'''
else:
    new='''            sweep_a10_seen: 0,\n            bench_tag: 0,\n            bench_phase: 0,\n            bench_boot_tick: 0,\n            bench_start_tick: 0,\n            bench_elapsed_ticks: 0,\n            bench_start_advance: 0,\n            bench_adv_delta: 0,\n            bench_advance_events: 0,\n            bench_max_jump: 0,\n            bench_frame_samples: 0,\n            bench_exact_cells: 0,\n            bench_a10_count: 0,\n            bench_bucket_intervals: 0,\n            bench_bucket_ok: 0,\n            bench_bucket_bad: 0,\n            bench_last_a10_advance: 0,\n            bench_last_bucket: 0,\n            bench_last_bucket_valid: false,\n            bench_last_keys: 0,\n            bench_keys_or: 0,\n            bench_key_changes: 0,\n            bench_up_samples: 0,\n            bench_b_samples: 0,\n            bench_start_samples: 0,\n            bench_start_state: 0,\n            bench_start_div: 0,\n            bench_end_state: 0,\n            bench_end_div: 0,\n            phase_now_proto: b'?', '''
t=rep(t,old,new,'default fields')

# Every Y+direction benchmark start runs through start_practical_scan(). Read
# the C-side tag (M12..M15) before the scan is allowed to run.
old='''        self.sweep_a10_seen = 0;\n        self.phase_now_proto = b'?';'''
new='''        self.sweep_a10_seen = 0;\n        self.bench_tag = match pnp::fixed_a_frame().phase_slot & 15 {\n            13 => 1, 14 => 2, 15 => 3, _ => 0,\n        };\n        self.bench_phase = 0;\n        self.bench_boot_tick = 0;\n        self.bench_start_tick = 0;\n        self.bench_elapsed_ticks = 0;\n        self.bench_start_advance = 0;\n        self.bench_adv_delta = 0;\n        self.bench_advance_events = 0;\n        self.bench_max_jump = 0;\n        self.bench_frame_samples = 0;\n        self.bench_exact_cells = 0;\n        self.bench_a10_count = 0;\n        self.bench_bucket_intervals = 0;\n        self.bench_bucket_ok = 0;\n        self.bench_bucket_bad = 0;\n        self.bench_last_a10_advance = 0;\n        self.bench_last_bucket = 0;\n        self.bench_last_bucket_valid = false;\n        self.bench_last_keys = 0;\n        self.bench_keys_or = 0;\n        self.bench_key_changes = 0;\n        self.bench_up_samples = 0;\n        self.bench_b_samples = 0;\n        self.bench_start_samples = 0;\n        self.bench_start_state = 0;\n        self.bench_start_div = 0;\n        self.bench_end_state = 0;\n        self.bench_end_div = 0;\n        self.phase_now_proto = b'?';'''
t=rep(t,old,new,'scan reset')

start=t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
end=t.index('\n    fn practical_fail',start)

helper=r'''    fn save_legal_benchmark(&mut self) {
        const TPS:u64=268_123_480;
        let ticks=self.bench_elapsed_ticks.max(1);
        let advps100=((self.bench_adv_delta as u64).saturating_mul(TPS).saturating_mul(100)/ticks) as u32;
        let a10ps100=((self.bench_a10_count as u64).saturating_mul(TPS).saturating_mul(100)/ticks) as u32;
        let frameps100=((self.bench_frame_samples as u64).saturating_mul(TPS).saturating_mul(100)/ticks) as u32;
        if !pnp::trace_file_open(self.save_index) { self.save_result=Some(false); return; }
        let mut line=LineBuf::new();
        let _=write!(line,
            "legal_benchmark,version,tag,warmup_ms,measure_ms,elapsed_ticks,frame_samples,frame_per_sec_x100,start_advance,advance_delta,advance_per_sec_x100,advance_events,max_jump,exact_cells,a10_count,a10_per_sec_x100,bucket_intervals,bucket_ok,bucket_bad,keys_or,key_changes,up_samples,b_samples,start_samples,start_state,start_div,end_state,end_div\\nBENCH,V744,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:04X}\\n",
            self.bench_tag,2000,10000,ticks,self.bench_frame_samples,frameps100,
            self.bench_start_advance,self.bench_adv_delta,advps100,self.bench_advance_events,self.bench_max_jump,
            self.bench_exact_cells,self.bench_a10_count,a10ps100,self.bench_bucket_intervals,self.bench_bucket_ok,
            self.bench_bucket_bad,self.bench_keys_or,self.bench_key_changes,self.bench_up_samples,self.bench_b_samples,
            self.bench_start_samples,self.bench_start_state,self.bench_start_div,self.bench_end_state,self.bench_end_div);
        pnp::trace_file_write(line.as_bytes());
        pnp::trace_file_close();
        self.save_result=Some(true);
        self.save_index=self.save_index.wrapping_add(1);
    }

'''

newfn=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        const TPS:u64=268_123_480;
        const WARM:u64=2*TPS;
        const MEASURE:u64=10*TPS;
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid { return; }

        let now=pnp::system_tick();
        let cur=rng_advance();

        // Phase 0 is deliberately excluded from the result. It gives the user
        // two seconds to release the launch chord and establish the requested
        // ordinary game input/screen before timing starts.
        if self.bench_phase==0 {
            if self.bench_boot_tick==0 { self.bench_boot_tick=now; return; }
            self.bench_elapsed_ticks=now.wrapping_sub(self.bench_boot_tick);
            if self.bench_elapsed_ticks<WARM { return; }
            self.bench_phase=1;
            self.bench_start_tick=now;
            self.bench_elapsed_ticks=0;
            self.bench_start_advance=cur;
            self.bench_adv_delta=0;
            self.bench_advance_events=0;
            self.bench_max_jump=0;
            self.bench_frame_samples=0;
            self.bench_exact_cells=0;
            self.bench_a10_count=0;
            self.bench_bucket_intervals=0;
            self.bench_bucket_ok=0;
            self.bench_bucket_bad=0;
            self.bench_last_a10_advance=0;
            self.bench_last_bucket_valid=false;
            self.bench_last_keys=pnp::current_keys();
            self.bench_keys_or=0;
            self.bench_key_changes=0;
            self.bench_up_samples=0;
            self.bench_b_samples=0;
            self.bench_start_samples=0;
            self.bench_start_state=reader.rng_state();
            self.bench_start_div=measured_div();
            self.practical_live_last_advance=cur;
            return;
        }

        if self.bench_phase!=1 { return; }
        self.bench_elapsed_ticks=now.wrapping_sub(self.bench_start_tick);
        self.bench_adv_delta=cur.wrapping_sub(self.bench_start_advance);
        self.bench_frame_samples=self.bench_frame_samples.saturating_add(1);

        let keys=pnp::current_keys();
        self.bench_keys_or|=keys;
        if keys!=self.bench_last_keys {
            self.bench_key_changes=self.bench_key_changes.saturating_add(1);
            self.bench_last_keys=keys;
        }
        if (keys&0x40)!=0 { self.bench_up_samples=self.bench_up_samples.saturating_add(1); }
        if (keys&0x02)!=0 { self.bench_b_samples=self.bench_b_samples.saturating_add(1); }
        if (keys&0x08)!=0 { self.bench_start_samples=self.bench_start_samples.saturating_add(1); }

        if self.bench_elapsed_ticks>=MEASURE {
            self.bench_end_state=reader.rng_state();
            self.bench_end_div=measured_div();
            self.bench_phase=2;
            self.practical_live_found_advance=cur;
            self.practical_live_found_state=reader.rng_state();
            self.practical_live_found_div=measured_div();
            self.practical_live_found_lane=250; // benchmark complete; never encounter-arm
            self.practical_live_found_tick=now;
            self.practical_live_scan=false;
            self.practical_scan_enabled=false;
            pre_vblank_timing_capture_stop();
            self.save_legal_benchmark();
            pnp::request_pause();
            return;
        }

        let da=cur.wrapping_sub(self.practical_live_last_advance);
        if da==0 { return; }
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);
        self.bench_advance_events=self.bench_advance_events.saturating_add(1);
        if da>self.bench_max_jump { self.bench_max_jump=da; }

        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n!=PRE_VBLANK_RING_LEN { return; }
        let(last,_)=pre_ring_sample(&r,n-1);
        let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best; self.phase_second_score=second; self.phase_consecutive=ok;
        self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag.min(255)as u8;
        if lag==1 { rot=rot.wrapping_add(1)&15; }
        if lag!=0 || !ok || best!=0 { return; }
        self.bench_exact_cells=self.bench_exact_cells.saturating_add(1);
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);
        if proto0!=b'A' || rot!=10 { return; }
        let(_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0 { return; }
        let bucket=((pd>>6)&0xff)as u8;
        self.bucket_current=bucket;
        self.bench_a10_count=self.bench_a10_count.saturating_add(1);
        if self.bench_last_bucket_valid {
            let daa=cur.wrapping_sub(self.bench_last_a10_advance);
            let db=bucket.wrapping_sub(self.bench_last_bucket);
            self.bench_bucket_intervals=self.bench_bucket_intervals.saturating_add(1);
            if daa%16==0 && db==((37u32.wrapping_mul(daa/16))&255)as u8 {
                self.bench_bucket_ok=self.bench_bucket_ok.saturating_add(1);
            } else {
                self.bench_bucket_bad=self.bench_bucket_bad.saturating_add(1);
            }
        }
        self.bench_last_a10_advance=cur;
        self.bench_last_bucket=bucket;
        self.bench_last_bucket_valid=true;
    }
'''

t=t[:start]+helper+newfn+t[end:]

# Replace the v742 scan display with benchmark status, but retain all other
# v742 result/probe branches for safety/debugging.
start=t.index('    pub fn draw_rng_status(&self) {')
seg=t[start:]
a=seg.index('        if self.practical_scan_enabled {')
b=seg.index('        } else if self.practical_live_found_lane == 251',a)
oldprefix=seg[a:b]
newprefix=r'''        if self.practical_scan_enabled {
            let tag=match self.bench_tag {0=>"IDLE",1=>"UP HOLD",2=>"B MASH",_=>"MENU IDLE"};
            if self.bench_phase==0 {
                const TPS:u64=268_123_480;
                let ms=(self.bench_elapsed_ticks.saturating_mul(1000)/TPS).min(1999);
                pnp::println!("S744 LEGAL SPEED");
                pnp::println!("{} PREP {}.{:01}s",tag,ms/1000,(ms%1000)/100);
                pnp::println!("MEASURE STARTS AT 2s");
                pnp::println!("USE NORMAL INPUT ONLY");
            } else {
                const TPS:u64=268_123_480;
                let ticks=self.bench_elapsed_ticks.max(1);
                let advps100=((self.bench_adv_delta as u64).saturating_mul(TPS).saturating_mul(100)/ticks)as u32;
                let a10ps100=((self.bench_a10_count as u64).saturating_mul(TPS).saturating_mul(100)/ticks)as u32;
                let ms=(self.bench_elapsed_ticks.saturating_mul(1000)/TPS).min(10000);
                pnp::println!("S744 {} {}.{:01}/10s",tag,ms/1000,(ms%1000)/100);
                pnp::println!("ADV {} {}.{:02}/s",self.bench_adv_delta,advps100/100,advps100%100);
                pnp::println!("A10 {} {}.{:02}/s",self.bench_a10_count,a10ps100/100,a10ps100%100);
                pnp::println!("EV{} MAX{} K{:04X}",self.bench_advance_events,self.bench_max_jump,self.bench_keys_or&0xffff);
            }
'''
seg=seg[:a]+newprefix+seg[b:]
# Insert benchmark-done branch ahead of the inherited sweep-done branch.
needle='''        } else if self.practical_live_found_lane == 251 && !self.probe_session {'''
need(needle in seg,'lane251 UI anchor missing')
done=r'''        } else if self.practical_live_found_lane == 250 && !self.probe_session {
            const TPS:u64=268_123_480;
            let ticks=self.bench_elapsed_ticks.max(1);
            let advps100=((self.bench_adv_delta as u64).saturating_mul(TPS).saturating_mul(100)/ticks)as u32;
            let a10ps100=((self.bench_a10_count as u64).saturating_mul(TPS).saturating_mul(100)/ticks)as u32;
            pnp::println!("S744 BENCH DONE T{}",self.bench_tag);
            pnp::println!("ADV {} {}.{:02}/s",self.bench_adv_delta,advps100/100,advps100%100);
            pnp::println!("A10 {} {}.{:02}/s",self.bench_a10_count,a10ps100/100,a10ps100%100);
            pnp::println!("BKT OK{} BAD{}",self.bench_bucket_ok,self.bench_bucket_bad);
            pnp::println!("CSV {}",pnp::trace_written_slot());
'''
seg=seg.replace(needle,done+needle,1)
t=t[:start]+seg

# Dedicated benchmark launch keys inside the existing pause-loop Y block.
# They run before legacy Y+direction controls, so no frame-count setting or
# old B76/B39 scan is triggered. M12..M15 are only temporary tags consumed by
# start_practical_scan(); no Resume operation is performed in this build.
anchor='''        if (held & KEY_Y)\n        {\n'''
need(m.count(anchor)==1,'Y pause block anchor missing')
block='''        if (held & KEY_Y)\n        {\n            if (just_pressed & (KEY_DDOWN | KEY_DUP | KEY_DLEFT | KEY_DRIGHT))\n            {\n                suicune_root_lock_active = false;\n                suicune_root_lock_ready = false;\n                suicune_root_lock_failed = false;\n                suicune_wait_up_after_b = false;\n                suicune_root_lock_steps = 0;\n                suicune_root_lock_last_cell = 0;\n                if (just_pressed & KEY_DDOWN) suicune_phase_slot = 12U; // IDLE\n                else if (just_pressed & KEY_DUP) suicune_phase_slot = 13U; // UP HOLD\n                else if (just_pressed & KEY_DLEFT) suicune_phase_slot = 14U; // B MASH\n                else suicune_phase_slot = 15U; // MENU IDLE\n                search_suicune_practical_targets();\n                is_paused = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                suicune_auto_resume_pending = false;\n                suicune_phase_lock_active = false;\n                break;\n            }\n'''
m=m.replace(anchor,block,1)

T.write_text(t); M.write_text(m)
print('Applied v7.4.4 Legal Advance Speed Benchmark: 2s warmup + 10s physical-input ADV/A10 benchmark with auto CSV')
