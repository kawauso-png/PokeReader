#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
trace_path = Path('reader_core/src/crystal/trace.rs')
m = main_path.read_text()
t = trace_path.read_text()

def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# Six high-information calibration runs: E08 x3 then E09 x3.
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
'''    // v6.0: the parity selector was falsified by 0067-0071. Use the slot
    // already latched at Y+X from the six-run calibration sequence.
    suicune_early_profile_used = suicune_early_profile_next % 6;
    suicune_early_slot_used = suicune_early_phase_slot;''',
'remove v58 parity selector')
m = rep(m,
'''    // v5.8 adaptive mode does not consume the v5.7 sweep sequence.
    if (!suicune_early_control_enabled) return;''',
'''    // Consume only a real 13th-rel26 gate. Failed/retried arms do not skip.
    if (suicune_early_gate_requests == 1)
        suicune_early_profile_next = (suicune_early_profile_next + 1) % 6;
    if (!suicune_early_control_enabled) return;''',
'v60 consume real gate only')

# Current emulator M-cycle byte. ASUB/SSUB are last-VBlank values and remain
# stale during the repeated-rel26 stall.
t = rep(t, 'const STARTSIG_CPU_CTX_LEN: usize = 64;', '''const STARTSIG_CPU_CTX_LEN: usize = 64;
const LIVE_MCYCLE_SUBTICK_ADDR: u32 = 0x0022f604;''', 'live subtick address')
t = rep(t, '''    early_pre: EarlyLabPoint,
    early_post1: EarlyLabPoint,''', '''    early_pre: EarlyLabPoint,
    // v6.0: exact 13th-rel26 live phase; deliberately only direct host reads.
    early_live_valid: u8,
    early_live_div: u8,
    early_live_sub: u8,
    early_live_phase: u16,
    early_live_tick: u64,
    early_post1: EarlyLabPoint,''', 'add live fields')
t = rep(t, '''            early_pre: EarlyLabPoint::default(),
            early_post1: EarlyLabPoint::default(),''', '''            early_pre: EarlyLabPoint::default(),
            early_live_valid: 0,
            early_live_div: 0,
            early_live_sub: 0,
            early_live_phase: 0,
            early_live_tick: 0,
            early_post1: EarlyLabPoint::default(),''', 'init live fields')
t = rep(t, '''        self.early_pre = EarlyLabPoint::default();
        self.early_post1 = EarlyLabPoint::default();''', '''        self.early_pre = EarlyLabPoint::default();
        self.early_live_valid = 0;
        self.early_live_div = 0;
        self.early_live_sub = 0;
        self.early_live_phase = 0;
        self.early_live_tick = 0;
        self.early_post1 = EarlyLabPoint::default();''', 'reset live fields')
t = rep(t, '''                if self.early_rel26_count == 13 {
                    self.early_gate_seen = true;
                    self.early_pre = early_point(e);
                    pnp::request_suicune_early_gate(self.early_pre.ap4);
                }''', '''                if self.early_rel26_count == 13 {
                    self.early_gate_seen = true;
                    self.early_pre = early_point(e);
                    // Unlike early_pre, these are sampled NOW at the 13th rel26.
                    // reader.div() resolves the emulator rDIV backing byte via
                    // direct host memory; no GB memory dispatcher is involved.
                    self.early_live_valid = 1;
                    self.early_live_div = reader.div();
                    self.early_live_sub = pnp::read::<u8>(LIVE_MCYCLE_SUBTICK_ADDR);
                    self.early_live_phase = direct_phase_m(self.early_live_div, self.early_live_sub);
                    self.early_live_tick = pnp::system_tick();
                    pnp::request_suicune_early_gate(self.early_pre.ap4);
                }''', 'capture exact live phase')

old_profile = '''        let profile = match em.pre_div_parity {
            0 => "EVEN",
            1 => "ODD",
            _ => "?",
        };'''
new_profile = '''        let profile = match em.profile_used {
            0 => "A", 1 => "B", 2 => "C", 3 => "D", 4 => "E", 5 => "F", _ => "?",
        };'''
if t.count(old_profile) != 2:
    raise SystemExit(f'profile blocks: expected 2 matches, got {t.count(old_profile)}')
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
            "live_phase,version,profile,slot,valid,live_div,live_sub,live_phase,live_tick,stale_ap4,stale_atick,stale_age_ticks,post1_ap4,live_to_post1\n"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "LIVE,V60,{},{},{},{:02X},{:02X},{:04X},{},{:04X},{},{},{:04X},{}\n",
            profile, em.used_slot, self.early_live_valid, self.early_live_div, self.early_live_sub,
            self.early_live_phase, self.early_live_tick, self.early_pre.ap4,
            self.early_pre.atick, stale_age, self.early_post1.ap4, live_to_post1
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let request_from_anchor = em.request_tick as i128 - em.anchor as i128;'''
t = rep(t, needle, insert, 'insert LIVE V60 row')

main_path.write_text(m)
trace_path.write_text(t)
print('Applied Suicune v6.0 core live-phase probe')
