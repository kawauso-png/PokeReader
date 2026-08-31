#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
hook_path = Path('reader_core/src/crystal/hook.rs')
trace_path = Path('reader_core/src/crystal/trace.rs')

m = main_path.read_text()
h = hook_path.read_text()
t = trace_path.read_text()

def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v6.0 Early Live Phase Probe: E08 x3, then E09 x3.
# Profiles advance only on a real 13th-rel26 gate request.
m = rep(m,
'''    static const u32 profile_slots[10] = {8, 9, 8, 9, 7, 10, 6, 11, 5, 12};''',
'''    static const u32 profile_slots[6] = {8, 8, 8, 9, 9, 9};''',
'v60 six-profile slots')
m = rep(m,
'''    suicune_early_profile_used = suicune_early_profile_next % 10;''',
'''    suicune_early_profile_used = suicune_early_profile_next % 6;''',
'v60 reset modulo')
m = rep(m,
'''    // Closed-loop rule from 0060-0066: odd DIV -> E08, even DIV -> E09.
    suicune_early_phase_slot = suicune_early_pre_div_parity ? 8 : 9;
    suicune_early_slot_used = suicune_early_phase_slot;
    // A = even/E09, B = odd/E08.  v5.7's wider profile sequence is bypassed
    // in adaptive mode but its telemetry plumbing is retained.
    suicune_early_profile_used = suicune_early_pre_div_parity ? 1 : 0;''',
'''    // v6.0: use the profile latched at Y+X. The old parity selector was
    // falsified by 0067-0071 and is retained only as historical telemetry.
    suicune_early_profile_used = suicune_early_profile_next % 6;
    suicune_early_slot_used = suicune_early_phase_slot;''',
'remove v58 parity selector')
m = rep(m,
'''    // v5.8 adaptive mode does not consume the v5.7 sweep sequence.
    if (!suicune_early_control_enabled) return;''',
'''    // Consume only a real gate; failed/retried Y+X arms keep the same slot.
    if (suicune_early_gate_requests == 1)
        suicune_early_profile_next = (suicune_early_profile_next + 1) % 6;
    if (!suicune_early_control_enabled) return;''',
'restore six-profile consumption')

# Keep the useful v5.9 final-Random calibration sentinel, but leave Endpoint
# itself on the original v5.8 manual-R path (no Q wall-clock controller).
h = rep(h, 'static mut ENDPOINT_FAST_CALLS: u8 = 0;', '''static mut ENDPOINT_FAST_CALLS: u8 = 0;
const ENDPOINT_TAIL_SAMPLE_LEN: usize = 8;
static mut ENDPOINT_TAIL_SAMPLE_COUNT: u8 = 0;
static mut ENDPOINT_TAIL_PC: [u16; ENDPOINT_TAIL_SAMPLE_LEN] = [0; ENDPOINT_TAIL_SAMPLE_LEN];
static mut ENDPOINT_TAIL_DIV: [u8; ENDPOINT_TAIL_SAMPLE_LEN] = [0; ENDPOINT_TAIL_SAMPLE_LEN];''', 'tail buffers')
h = rep(h, '''        ENDPOINT_FAST_CALLS = 0;
        ENDPOINT_FAST_TAIL = true;''', '''        ENDPOINT_FAST_CALLS = 0;
        ENDPOINT_TAIL_SAMPLE_COUNT = 0;
        ENDPOINT_FAST_TAIL = true;''', 'reset tail sentinel')
h = rep(h, '''pub fn endpoint_fast_tail_calls() -> u8 {
    unsafe { ENDPOINT_FAST_CALLS }
}

pub fn endpoint_fast_tail_stop() {''', '''pub fn endpoint_fast_tail_calls() -> u8 {
    unsafe { ENDPOINT_FAST_CALLS }
}

pub fn endpoint_tail_sample_count() -> u8 {
    unsafe { ENDPOINT_TAIL_SAMPLE_COUNT }
}

pub fn endpoint_tail_sample(index: usize) -> (u16, u8) {
    unsafe {
        if index >= ENDPOINT_TAIL_SAMPLE_COUNT as usize || index >= ENDPOINT_TAIL_SAMPLE_LEN {
            return (0, 0);
        }
        (ENDPOINT_TAIL_PC[index], ENDPOINT_TAIL_DIV[index])
    }
}

pub fn endpoint_fast_tail_stop() {''', 'expose tail sentinel')
h = rep(h, '''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        // Count only Random's first rDIV read.  No DIV/state/tick/mcycle reads
        // are performed in PURETAIL mode; this single host byte increment is
        // retained solely to distinguish the 3-call and 4-call item branch.
        if pc == 0x2f60 {
            unsafe { ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1) };
        }
        return;
    }''', '''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        // Calibration-only: one rDIV read plus tiny stores. No host tick,
        // mcycle, RNG state, stack, CPU context or Deep/CALL log work.
        let div = reader.div();
        unsafe {
            let idx = ENDPOINT_TAIL_SAMPLE_COUNT as usize;
            if idx < ENDPOINT_TAIL_SAMPLE_LEN {
                ENDPOINT_TAIL_PC[idx] = pc;
                ENDPOINT_TAIL_DIV[idx] = div;
                ENDPOINT_TAIL_SAMPLE_COUNT = ENDPOINT_TAIL_SAMPLE_COUNT.saturating_add(1);
            }
            if pc == 0x2f60 {
                ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1);
            }
        }
        return;
    }''', 'lightweight tail DIV sampling')

# The old early_pre AP4 is a last-VBlank carryover during rel26. Capture the
# emulator's actual current rDIV and M-cycle subtick exactly at the 13th rel26.
t = rep(t, '''    endpoint_fast_tail_start, endpoint_fast_tail_stop, measured_div, rng_advance, sdiv_cycles,
    sdiv_subtick, sdiv_tick, sub_div_tracker,''', '''    endpoint_fast_tail_start, endpoint_fast_tail_stop, endpoint_tail_sample,
    endpoint_tail_sample_count, measured_div, rng_advance, sdiv_cycles, sdiv_subtick, sdiv_tick,
    sub_div_tracker,''', 'import tail sentinel')
t = rep(t, 'const STARTSIG_CPU_CTX_LEN: usize = 64;', '''const STARTSIG_CPU_CTX_LEN: usize = 64;
// JP VC emulator-side current LR35902 M-cycle position. Unlike ASUB/SSUB this
// is read live at the 13th rel26 gate rather than carried from the last VBlank.
const LIVE_MCYCLE_SUBTICK_ADDR: u32 = 0x0022f604;''', 'live subtick address')
t = rep(t, '''    early_pre: EarlyLabPoint,
    early_post1: EarlyLabPoint,''', '''    early_pre: EarlyLabPoint,
    // v6.0 exact 13th-rel26 live snapshot; early_pre remains for stale comparison.
    early_live_valid: u8,
    early_live_div: u8,
    early_live_sub: u8,
    early_live_phase: u16,
    early_live_state: u16,
    early_live_tick: u64,
    early_post1: EarlyLabPoint,''', 'add live phase fields')
t = rep(t, '''            early_pre: EarlyLabPoint::default(),
            early_post1: EarlyLabPoint::default(),''', '''            early_pre: EarlyLabPoint::default(),
            early_live_valid: 0,
            early_live_div: 0,
            early_live_sub: 0,
            early_live_phase: 0,
            early_live_state: 0,
            early_live_tick: 0,
            early_post1: EarlyLabPoint::default(),''', 'init live phase fields')
t = rep(t, '''        self.early_pre = EarlyLabPoint::default();
        self.early_post1 = EarlyLabPoint::default();''', '''        self.early_pre = EarlyLabPoint::default();
        self.early_live_valid = 0;
        self.early_live_div = 0;
        self.early_live_sub = 0;
        self.early_live_phase = 0;
        self.early_live_state = 0;
        self.early_live_tick = 0;
        self.early_post1 = EarlyLabPoint::default();''', 'reset live phase fields')
t = rep(t, '''                if self.early_rel26_count == 13 {
                    self.early_gate_seen = true;
                    self.early_pre = early_point(e);
                    pnp::request_suicune_early_gate(self.early_pre.ap4);
                }''', '''                if self.early_rel26_count == 13 {
                    self.early_gate_seen = true;
                    self.early_pre = early_point(e);
                    self.early_live_valid = 1;
                    self.early_live_div = reader.div();
                    self.early_live_sub = pnp::read::<u8>(LIVE_MCYCLE_SUBTICK_ADDR);
                    self.early_live_phase = direct_phase_m(self.early_live_div, self.early_live_sub);
                    self.early_live_state = reader.rng_state();
                    self.early_live_tick = pnp::system_tick();
                    pnp::request_suicune_early_gate(self.early_pre.ap4);
                }''', 'capture exact 13th-rel26 live phase')

old_profile = '''        let profile = match em.pre_div_parity {
            0 => "EVEN",
            1 => "ODD",
            _ => "?",
        };'''
new_profile = '''        let profile = match em.profile_used {
            0 => "A", 1 => "B", 2 => "C", 3 => "D", 4 => "E", 5 => "F", _ => "?",
        };'''
if t.count(old_profile) != 2:
    raise SystemExit(f'profile label blocks: expected 2, got {t.count(old_profile)}')
t = t.replace(old_profile, new_profile)
t = t.replace('ADAPT,V58,', 'PLAN,V60,')
t = t.replace('MAP,V58,', 'MAP,V60,')
t = t.replace('EARLY,V58,', 'EARLY,V60,')

needle = '''        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let request_from_anchor = em.request_tick as i128 - em.anchor as i128;'''
insert = '''        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let stale_age = self.early_live_tick.saturating_sub(self.early_pre.atick);
        let live_to_post1 = if self.early_live_valid != 0 && self.early_post1.valid != 0 {
            phase_step_m(self.early_live_phase, self.early_post1.ap4)
        } else { 0 };
        let _ = write!(line,
            "live_phase,version,profile,slot,valid,live_div,live_sub,live_phase,live_state,live_tick,stale_ap4,stale_atick,stale_age_ticks,post1_ap4,live_to_post1\n"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "LIVE,V60,{},{},{},{:02X},{:02X},{:04X},{:04X},{},{:04X},{},{},{:04X},{}\n",
            profile, em.used_slot, self.early_live_valid, self.early_live_div, self.early_live_sub,
            self.early_live_phase, self.early_live_state, self.early_live_tick,
            self.early_pre.ap4, self.early_pre.atick, stale_age,
            self.early_post1.ap4, live_to_post1
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let request_from_anchor = em.request_tick as i128 - em.anchor as i128;'''
t = rep(t, needle, insert, 'insert LIVE V60 CSV row')

needle = '''        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\n"
        );'''
insert = '''        line.clear();
        let _ = write!(line, "tail_index,pc,div\n");
        pnp::trace_file_write(line.as_bytes());
        for ti in 0..endpoint_tail_sample_count() as usize {
            let (pc, div) = endpoint_tail_sample(ti);
            line.clear();
            let _ = write!(line, "{},{:04X},{:02X}\n", ti, pc, div);
            pnp::trace_file_write(line.as_bytes());
        }
        line.clear();
        let _ = write!(line, "\n");
        pnp::trace_file_write(line.as_bytes());
        line.clear();

        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\n"
        );'''
t = rep(t, needle, insert, 'append tail samples')

main_path.write_text(m)
hook_path.write_text(h)
trace_path.write_text(t)
print('Applied Suicune v6.0 Early Live Phase Probe')
