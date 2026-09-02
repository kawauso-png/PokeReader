#!/usr/bin/env python3
from pathlib import Path

H=Path('reader_core/src/crystal/hook.rs')
T=Path('reader_core/src/crystal/trace.rs')
h=H.read_text(); t=T.read_text()

def need(x,m,label):
    if m not in x: raise SystemExit('v731 missing '+label+': '+m)
def rep(x,a,b,label,count=1):
    n=x.count(a)
    if n!=count: raise SystemExit(f'v731 {label}: expected {count}, got {n}')
    return x.replace(a,b,count)
def span(x,sig):
    s=x.find(sig)
    if s<0: raise SystemExit('v731 function not found: '+sig)
    b=x.find('{',s); d=0
    for i in range(b,len(x)):
        if x[i]=='{': d+=1
        elif x[i]=='}':
            d-=1
            if d==0:return s,i+1
    raise SystemExit('v731 unclosed: '+sig)

# -------------------------------------------------------------------------
# Hook side: detect a *paired* A/S VBlank DIV discontinuity, but do not reset
# anything in the hook itself. Encounter stop1/stop2 can create the same large
# DIV gap, so Trace decides whether the discontinuity happened in a safe SCAN
# context before treating it as a VC software reset.
# -------------------------------------------------------------------------
need(h,'static mut ADD_DIV_TRACKER: DivTracker = DivTracker::new();','DIV trackers')
need(h,'static mut PRE_VBLANK_RING: PreVBlankRing = PreVBlankRing::EMPTY;','PRE ring')
need(h,'static mut V53_HITS: u32 = 0;','v53 context diagnostics')
need(h,'static mut ENDPOINT_FAST_TAIL: bool = false;','PURETAIL state')

hook_state=r'''
// v7.3.1 VC software-reset detector. A single long gap is only evidence, not
// proof: Suicune's encounter stalls also stop the VBlank RNG routine. We expose
// an epoch for paired A/S discontinuities and let Trace consume it only while
// no encounter execution is active.
static mut VC_DIV_DISCONT_EPOCH: u32 = 0;
static mut VC_DIV_A_BAD: bool = false;
static mut VC_DIV_A_ADV: u32 = 0;

pub fn vc_div_discontinuity_epoch() -> u32 { unsafe { VC_DIV_DISCONT_EPOCH } }

#[inline]
fn vc_div_gap_bad(last: u8, now: u8, old_advance: u32) -> bool {
    if old_advance < 64 { return false; }
    let d = now.wrapping_sub(last);
    d != 0x12 && d != 0x13
}

/// Wipe every observer whose value is meaningful only inside one VC boot.
/// The discontinuity epoch itself is intentionally preserved so Trace can
/// acknowledge exactly which reset it consumed.
pub fn reset_vc_session_observers() {
    unsafe {
        RNG_ADVANCE = 0;
        ADIV = 0; SDIV = 0;
        CYCLE_COUNTER = 0; ACYCLES = 0; SCYCLES = 0;
        ASUB = 0; SSUB = 0; ATICKS = 0; STICKS = 0;
        FF04_HITS = 0; ANY_HITS = 0; LAST_PC = 0; PC_SEEN_1 = 0; PC_SEEN_2 = 0;
        ADD_DIV_TRACKER = DivTracker::new();
        SUB_DIV_TRACKER = DivTracker::new();
        PRE_VBLANK_RING = PreVBlankRing::EMPTY;
        LAST_VBLANK_CONTEXT = VBlankContextSnapshot::EMPTY;
        VBLANK_CONTEXT_CAPTURE_ENABLED = true;
        V53_HITS = 0; V53_WRITES = 0; V53_VALID = 0; V53_COMPLETE = 0;
        V53_CTX_MAPPED = 0; V53_PC = 0; V53_ADVANCE = 0; V53_DIV = 0;
        V53_MCYCLE = 0; V53_HOST_TICK = 0;
        V53_CPU_CTX = [0; VBLANK_CTX_LEN];
        V53_REGS = [0; VBLANK_ARM_REGS];
        V53_STACK = [0; VBLANK_STACK_WORDS];
        CALL_WRITE = 0; CALL_COUNT = 0; CALL_LOGGING = false;
        DEEP_WRITE = 0; DEEP_COUNT = 0; DEEP_LOGGING = false;
        ENDPOINT_FAST_TAIL = false;
        VC_DIV_A_BAD = false; VC_DIV_A_ADV = 0;
    }
    diff_probe_clear();
}
'''
anchor='pub fn rng_advance() -> u32 {\n'
need(h,anchor,'rng advance getter')
h=h.replace(anchor,hook_state+'\n'+anchor,1)

old_a='''    if RNG_DIV_READ_1.contains(&pc) {
        let div = reader.div();
        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle);'''
new_a='''    if RNG_DIV_READ_1.contains(&pc) {
        let div = reader.div();
        let old_advance = unsafe { RNG_ADVANCE };
        let a_bad = unsafe { vc_div_gap_bad(ADD_DIV_TRACKER.last_div, div, old_advance) };
        unsafe {
            VC_DIV_A_BAD = a_bad;
            VC_DIV_A_ADV = old_advance.wrapping_add(1);
        }
        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle);'''
h=rep(h,old_a,new_a,'A discontinuity detector')

old_s='''    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();'''
new_s='''    if RNG_DIV_READ_2.contains(&pc) {
        let div = reader.div();
        let now_advance = unsafe { RNG_ADVANCE };
        let s_bad = unsafe { vc_div_gap_bad(SUB_DIV_TRACKER.last_div, div, now_advance.saturating_sub(1)) };
        unsafe {
            if s_bad && VC_DIV_A_BAD && VC_DIV_A_ADV == now_advance {
                VC_DIV_DISCONT_EPOCH = VC_DIV_DISCONT_EPOCH.wrapping_add(1);
            }
            VC_DIV_A_BAD = false;
        }'''
h=rep(h,old_s,new_s,'S discontinuity detector')
H.write_text(h)

# -------------------------------------------------------------------------
# Trace side: consume a discontinuity only when an encounter is NOT executing.
# A consumed reset replaces all Trace/practical runtime with Default, preserving
# only file slot/watch address. Host request IDs are synchronized so old queued
# commands cannot leak into the fresh session.
# -------------------------------------------------------------------------
need(t,'practical_global_speculative: bool,','v730 field')
need(t,'S730 TEST UP+B','current physical protocol')
need(t,'fn practical_wait_monitor','GlobalBeam monitor')

# Import the hook reset/epoch helpers without depending on the evolving import
# line layout.
ib=t.find('use super::hook::{'); ie=t.find('};',ib)
if ib<0 or ie<0: raise SystemExit('v731 hook import block')
if 'vc_div_discontinuity_epoch' not in t[ib:ie]:
    t=t[:ie]+'    reset_vc_session_observers, vc_div_discontinuity_epoch,\n'+t[ie:]

t=rep(t,'    practical_global_speculative: bool,\n    practical_post_proto: u8,','''    practical_global_speculative: bool,
    soft_reset_seen_epoch: u32,
    soft_reset_count: u32,
    soft_reset_rearm_pending: bool,
    soft_reset_saw_unloaded: bool,
    soft_reset_loaded_streak: u8,
    soft_reset_expected_tid: u16,
    soft_reset_play_marker: u32,
    practical_post_proto: u8,''','soft reset fields')
t=rep(t,'            practical_global_speculative: false,\n            practical_post_proto: 0,','''            practical_global_speculative: false,
            soft_reset_seen_epoch: 0,
            soft_reset_count: 0,
            soft_reset_rearm_pending: false,
            soft_reset_saw_unloaded: false,
            soft_reset_loaded_streak: 0,
            soft_reset_expected_tid: 0,
            soft_reset_play_marker: 0,
            practical_post_proto: 0,''','soft reset defaults')
# Ordinary new search must leave reset-wait mode.
search_s,search_e=span(t,'    pub fn search_practical_targets')
search=t[search_s:search_e]
needle='        self.practical_search_error = 0;\n'
need(search,needle,'search reset anchor')
search=search.replace(needle,needle+'        self.soft_reset_rearm_pending = false;\n        self.soft_reset_loaded_streak = 0;\n',1)
t=t[:search_s]+search+t[search_e:]

helpers=r'''
    fn sync_host_command_ids(&mut self) {
        let (arm_id, _) = pnp::trace_request();
        let (stop_req, save_req) = pnp::trace_cmds();
        self.last_arm_id = arm_id;
        self.last_stop_req = stop_req;
        self.last_save_req = save_req;
        self.last_run_id = pnp::fixed_run_id();
    }

    #[inline]
    fn play_marker(reader: &Gen2Reader) -> u32 {
        ((reader.play_hours() as u32) << 16)
            | ((reader.play_minutes() as u32) << 8)
            | reader.play_seconds() as u32
    }

    fn soft_reset_save_loaded(&self, reader: &Gen2Reader) -> bool {
        // JP Crystal: wPartyMon1=DCA5 in the reader, therefore wPartyCount is
        // DC9D and the first species byte is DC9E. Requiring the same TID plus
        // a sane party and clock rejects title/boot WRAM before auto-SCAN.
        let party_count = gb_mem::read_u8(0xdc9d);
        let first_species = gb_mem::read_u8(0xdc9e);
        reader.trainer_id() == self.soft_reset_expected_tid
            && (1..=6).contains(&party_count)
            && (1..=251).contains(&first_species)
            && reader.play_minutes() < 60
            && reader.play_seconds() < 60
    }

    /// Returns true while the current frame must be kept out of the old
    /// session. A paired DIV gap during an active encounter is acknowledged but
    /// deliberately ignored: stop1/stop2 produce legitimate large DIV gaps.
    fn handle_vc_soft_reset(&mut self, reader: &Gen2Reader) -> bool {
        let epoch = vc_div_discontinuity_epoch();
        if epoch != self.soft_reset_seen_epoch {
            self.soft_reset_seen_epoch = epoch;
            let encounter_executing = self.probe_active || self.practical_active;
            let has_session = self.practical_live_scan
                || self.practical_search_enabled
                || self.practical_candidate_valid
                || self.practical_miss != 0
                || self.probe_session;
            if has_session && !encounter_executing {
                let keep_save_index = self.save_index;
                let keep_watch_addr = self.watch_addr;
                let next_count = self.soft_reset_count.saturating_add(1);
                let expected_tid = reader.trainer_id();
                let old_play = Self::play_marker(reader);

                call_log_stop();
                deep_log_stop();
                reset_vc_session_observers();

                // Default is the authoritative list of every runtime field.
                // Rebuilding from it prevents a newly-added v7.x counter from
                // silently surviving a later software reset.
                let mut fresh = Self::default();
                fresh.save_index = keep_save_index;
                fresh.watch_addr = keep_watch_addr;
                fresh.soft_reset_seen_epoch = epoch;
                fresh.soft_reset_count = next_count;
                fresh.soft_reset_rearm_pending = true;
                fresh.soft_reset_expected_tid = expected_tid;
                fresh.soft_reset_play_marker = old_play;
                // Keep the status in the SCAN UI branch, but the live monitor
                // is disabled until the loaded-save gate below succeeds.
                fresh.practical_search_enabled = true;
                fresh.practical_live_scan = false;
                fresh.practical_live_last_advance = u32::MAX;
                fresh.practical_live_start_advance = 0;
                fresh.practical_live_start_tick = pnp::system_tick();
                *self = fresh;
                self.sync_host_command_ids();
                pnp::request_resume();
                return true;
            }
        }

        if !self.soft_reset_rearm_pending { return false; }
        self.sync_host_command_ids();

        let loaded = self.soft_reset_save_loaded(reader);
        if !loaded {
            self.soft_reset_saw_unloaded = true;
            self.soft_reset_loaded_streak = 0;
            return true;
        }

        // If WRAM was visibly cleared, a valid signature is enough. If the VC
        // happened to preserve those bytes through reset, require play time to
        // move before trusting them. In both cases PRE must be freshly rebuilt.
        let play_moved = Self::play_marker(reader) != self.soft_reset_play_marker;
        let boot_transition_seen = self.soft_reset_saw_unloaded || play_moved;
        let pre_fresh = self.live_pre_cell().is_some();
        if boot_transition_seen && pre_fresh {
            self.soft_reset_loaded_streak = self.soft_reset_loaded_streak.saturating_add(1);
        } else {
            self.soft_reset_loaded_streak = 0;
        }

        if self.soft_reset_loaded_streak < 8 { return true; }

        self.soft_reset_rearm_pending = false;
        self.soft_reset_loaded_streak = 0;
        self.search_practical_targets(reader);
        false
    }

'''
rec=t.find('    pub fn record(&mut self, reader: &Gen2Reader) {')
if rec<0: raise SystemExit('v731 record function')
t=t[:rec]+helpers+t[rec:]
rec_anchor='''    pub fn record(&mut self, reader: &Gen2Reader) {
'''
t=rep(t,rec_anchor,rec_anchor+'''        if self.handle_vc_soft_reset(reader) {
            return;
        }
''','early soft-reset handler')

# Version/UI. RESET WAIT stays in the same branch as SCAN because
# practical_search_enabled is intentionally held true while live_scan=false.
t=t.replace('"S730 ','"S731 ')
scan='                pnp::println!("S731 SCAN");'
need(t,scan,'S731 scan label')
t=t.replace(scan,'''                if self.soft_reset_rearm_pending {
                    pnp::println!("S731 RESET WAIT");
                    pnp::println!("RST{} E{}", self.soft_reset_count, self.soft_reset_seen_epoch);
                } else {
                    pnp::println!("S731 SCAN");
                }''',1)
t=t.replace('GLOBALBEAM,V730','GLOBALBEAM,V731')

# Saved candidate traces record whether one or more software-reset epochs were
# consumed before this attempt. Keep it a separate row so existing V710 parsers
# do not need a schema change.
needle='let _=write!(line,"GLOBALBEAM,V731,'
pos=t.find(needle)
if pos<0: raise SystemExit('v731 GLOBALBEAM telemetry')
line_start=t.rfind('            ',0,pos)
insert='            let _=write!(line,"SOFTRESET,V731,{},{}\\n",self.soft_reset_count,self.soft_reset_seen_epoch);pnp::trace_file_write(line.as_bytes());line.clear();\n'
t=t[:line_start]+insert+t[line_start:]

for m in ['S731 TEST UP+B','S731 RESET WAIT','GLOBALBEAM,V731','SOFTRESET,V731','handle_vc_soft_reset','reset_vc_session_observers','vc_div_discontinuity_epoch']:
    need(t if m not in ['reset_vc_session_observers','vc_div_discontinuity_epoch'] else h,m,'postpatch '+m)
if 'S730 ' in t: raise SystemExit('v731 stale S730 UI')
T.write_text(t)
print('Applied Suicune v7.3.1 SoftReset Fresh: paired SCAN-only reset detection, full observer/runtime wipe, loaded-save gated auto re-SCAN; UP+B unchanged')
