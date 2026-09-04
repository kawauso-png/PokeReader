from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v768 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

h = rep(h,
'use super::reader::Gen2Reader;\nuse crate::{pnp, utils};',
'use super::{game_lib::gb_mem, reader::Gen2Reader};\nuse crate::{pnp, utils};',
'hook imports')

h = rep(h,
'''const LIVE_MASK_FRAMES: u32 = 16;
const LIVE_PASS_FRAMES: u32 = 2;
const LIVE_POST_FRAMES: u32 = 4;
const LIVE_SAMPLE_CAP: usize = 22;
const JOY_HJOY_DOWN: usize = 6; // FFA8
const RJOYP_ADDR: u32 = 0xff00;''',
'''const LIVE_MASK_FRAMES: u32 = 16;
const LIVE_PASS_FRAMES: u32 = 2;
const LIVE_POST_FRAMES: u32 = 4;
// Keep the probe alive through rel40.  The ordinary v7.6.6 rel40 diagnostic
// normally terminates first; 48 input advances is only a fail-safe horizon.
const LIVE_SAMPLE_CAP: usize = 48;
const LIVE_RJOYP_EVENT_CAP: usize = 128;
const JOY_HJOY_DOWN: usize = 6; // FFA8
const RJOYP_ADDR: u32 = 0xff00;

#[derive(Clone, Copy)]
pub struct RJoyEvent {
    pub rel_advance: u8,
    pub mode: u8, // 0=pre-mask, 1=pass, 2=post-mask
    pub redirected: u8,
    pub requested: u16,
    pub effective: u16,
    pub host_keys: u32,
    pub tick: u64,
    pub mcycle: u8,
    pub div: u8,
    pub phase4: u16,
    pub gb_pc: u16,
    pub r1: u32,
    pub r2: u32,
    pub r3: u32,
    pub r4: u32,
    pub r12: u32,
    pub lr: u32,
    pub host_pc: u32,
}

impl RJoyEvent {
    const EMPTY: Self = Self {
        rel_advance: 0, mode: 0, redirected: 0, requested: 0, effective: 0,
        host_keys: 0, tick: 0, mcycle: 0, div: 0, phase4: 0, gb_pc: 0,
        r1: 0, r2: 0, r3: 0, r4: 0, r12: 0, lr: 0, host_pc: 0,
    };
}''',
'constants/events')

h = rep(h,
'''    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
}''',
'''    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
    pub neutral_addr: u16,
    pub neutral_value: u8,
    pub neutral_ok: u8,
    pub redirected_rjoy_reads: u32,
    pub passthrough_rjoy_reads: u32,
}''',
'telemetry neutral fields')

h = rep(h,
'''        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
    };''',
'''        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
        neutral_addr: 0,
        neutral_value: 0,
        neutral_ok: 0,
        redirected_rjoy_reads: 0,
        passthrough_rjoy_reads: 0,
    };''',
'telemetry neutral defaults')

h = rep(h,
'''static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;
static mut LIVE_PASS_BEGIN_FAILURE_BASE: u16 = 0;
static mut LIVE_PASS_RESTORE_FAILURE_BASE: u16 = 0;''',
'''static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;
static mut LIVE_RJOYP_EVENTS: [RJoyEvent; LIVE_RJOYP_EVENT_CAP] = [RJoyEvent::EMPTY; LIVE_RJOYP_EVENT_CAP];
static mut LIVE_RJOYP_EVENT_COUNT: usize = 0;

fn find_neutral_rom0() -> Option<(u16, u8)> {
    // Fixed ROM0 is bank-stable.  0xFF has low nibble 0xF, which Crystal's
    // active-low rJOYP decoder interprets as no pressed directions/buttons.
    // Scan only while paused at B-ARM; the live path does no search.
    for addr in 0u32..=0x3fff {
        let v1 = gb_mem::read_u8(addr);
        if v1 == 0xff {
            let v2 = gb_mem::read_u8(addr);
            if v2 == 0xff {
                return Some((addr as u16, v1));
            }
        }
    }
    None
}

pub fn live_pass_rjoy_event_count() -> usize {
    unsafe { LIVE_RJOYP_EVENT_COUNT }
}

pub fn live_pass_rjoy_event(index: usize) -> Option<RJoyEvent> {
    unsafe {
        if index < LIVE_RJOYP_EVENT_COUNT && index < LIVE_RJOYP_EVENT_CAP {
            Some(LIVE_RJOYP_EVENTS[index])
        } else {
            None
        }
    }
}''',
'event storage/neutral finder')

old_arm = '''pub fn arm_live_pass_probe() -> bool {
    // There must be no transient mask left from an earlier aborted trial.
    let restored = pnp::hid_mask_up_restore();
    let capable = restored && pnp::hid_mask_capable();
    let (begin_base, restore_base) = pnp::hid_mask_stats();
    let base = rng_advance();
    unsafe {
        LIVE_PASS_BEGIN_FAILURE_BASE = begin_base;
        LIVE_PASS_RESTORE_FAILURE_BASE = restore_base;
        LIVE_PASS = LivePassTelemetry {
            armed_advance: base,
            first_input_advance: base.wrapping_add(1),
            pass_start_advance: base.wrapping_add(1 + LIVE_MASK_FRAMES),
            pass_end_advance: base.wrapping_add(1 + LIVE_MASK_FRAMES + LIVE_PASS_FRAMES),
            capable: capable as u8,
            ..LivePassTelemetry::EMPTY
        };
        LIVE_PASS_ARMED = capable;
    }
    capable
}

pub fn live_pass_telemetry() -> LivePassTelemetry {
    unsafe {
        let mut out = LIVE_PASS;
        let (bf, rf) = pnp::hid_mask_stats();
        out.begin_failures = bf.wrapping_sub(LIVE_PASS_BEGIN_FAILURE_BASE);
        out.restore_failures = rf.wrapping_sub(LIVE_PASS_RESTORE_FAILURE_BASE);
        out
    }
}'''
new_arm = '''pub fn arm_live_pass_probe() -> bool {
    // v7.6.8: fail closed unless a verified 0xFF byte exists in fixed ROM0.
    // No HID/shared-memory write is used by this architecture.
    let neutral = find_neutral_rom0();
    let base = rng_advance();
    unsafe {
        LIVE_RJOYP_EVENT_COUNT = 0;
        LIVE_RJOYP_EVENTS = [RJoyEvent::EMPTY; LIVE_RJOYP_EVENT_CAP];
        LIVE_PASS = LivePassTelemetry {
            armed_advance: base,
            first_input_advance: base.wrapping_add(1),
            pass_start_advance: base.wrapping_add(1 + LIVE_MASK_FRAMES),
            pass_end_advance: base.wrapping_add(1 + LIVE_MASK_FRAMES + LIVE_PASS_FRAMES),
            capable: neutral.is_some() as u8,
            neutral_addr: neutral.map(|x| x.0).unwrap_or(0),
            neutral_value: neutral.map(|x| x.1).unwrap_or(0),
            neutral_ok: neutral.is_some() as u8,
            ..LivePassTelemetry::EMPTY
        };
        LIVE_PASS_ARMED = neutral.is_some();
    }
    neutral.is_some()
}

pub fn live_pass_telemetry() -> LivePassTelemetry {
    unsafe { LIVE_PASS }
}'''
h = rep(h, old_arm, new_arm, 'arm/get telemetry')

h = rep(h,
'''        } else if after_pass {
            LIVE_PASS.game_remask_observed_advances = LIVE_PASS.game_remask_observed_advances.saturating_add(1);
            if LIVE_PASS.game_first_remask_hjoy == 0xff {
                LIVE_PASS.game_first_remask_hjoy = hjoy;
            }
            if up {
                LIVE_PASS.game_remask_up_advances = LIVE_PASS.game_remask_up_advances.saturating_add(1);
            }
        }''',
'''        } else if after_pass {
            let post_delta = now.wrapping_sub(LIVE_PASS.pass_end_advance);
            if post_delta < LIVE_POST_FRAMES {
                LIVE_PASS.game_remask_observed_advances = LIVE_PASS.game_remask_observed_advances.saturating_add(1);
                if LIVE_PASS.game_first_remask_hjoy == 0xff {
                    LIVE_PASS.game_first_remask_hjoy = hjoy;
                }
                if up {
                    LIVE_PASS.game_remask_up_advances = LIVE_PASS.game_remask_up_advances.saturating_add(1);
                }
            }
        }''',
'exact remask summary')

old_finish_filter = '''pub fn live_pass_should_finish() -> bool {
    unsafe {
        if !LIVE_PASS_ARMED {
            return false;
        }
        let finish = LIVE_PASS.pass_end_advance.wrapping_add(LIVE_POST_FRAMES - 1);
        RNG_ADVANCE.wrapping_sub(finish) < 0x8000_0000
    }
}

fn live_pass_restore_previous_mask() {
    unsafe {
        if !LIVE_PASS_ARMED {
            return;
        }
    }
    if !pnp::hid_mask_up_restore() {
        unsafe { LIVE_PASS_ARMED = false; }
        pnp::request_pause();
    }
}

fn live_pass_filter_rjoy(requested: u32) {
    if requested != RJOYP_ADDR {
        return;
    }

    unsafe {
        if !LIVE_PASS_ARMED {
            return;
        }

        LIVE_PASS.rjoy_reads = LIVE_PASS.rjoy_reads.wrapping_add(1);
        let now = RNG_ADVANCE;
        let pass_delta = now.wrapping_sub(LIVE_PASS.pass_start_advance);
        let in_pass = pass_delta < LIVE_PASS_FRAMES;
        let pc = Gen2Reader::crystal().pc_reg();

        if in_pass {
            LIVE_PASS.passed_rjoy_reads = LIVE_PASS.passed_rjoy_reads.wrapping_add(1);
            if LIVE_PASS.passed_advances == 0 || LIVE_PASS.last_pass_advance != now {
                LIVE_PASS.passed_advances = LIVE_PASS.passed_advances.saturating_add(1);
                LIVE_PASS.last_pass_advance = now;
            }
            if LIVE_PASS.first_pass_tick == 0 {
                let tick = pnp::system_tick();
                let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
                let div = Gen2Reader::crystal().div();
                LIVE_PASS.first_pass_advance = now;
                LIVE_PASS.first_pass_tick = tick;
                LIVE_PASS.first_pass_mcycle = mcycle;
                LIVE_PASS.first_pass_pc = pc;
                LIVE_PASS.first_pass_direct_div = div;
                LIVE_PASS.first_pass_phase4 = (((div as u16) << 6) | ((mcycle as u16) & 0x3f)) & 0x3fff;
            }
            return;
        }

        LIVE_PASS.masked_rjoy_reads = LIVE_PASS.masked_rjoy_reads.wrapping_add(1);
        if LIVE_PASS.masked_advances == 0 || LIVE_PASS.last_mask_advance != now {
            LIVE_PASS.masked_advances = LIVE_PASS.masked_advances.saturating_add(1);
            LIVE_PASS.last_mask_advance = now;
        }

        let after_pass = now.wrapping_sub(LIVE_PASS.pass_end_advance) < 0x8000_0000;
        if LIVE_PASS.first_mask_tick == 0 || (after_pass && LIVE_PASS.first_remask_tick == 0) {
            let tick = pnp::system_tick();
            let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
            if LIVE_PASS.first_mask_tick == 0 {
                LIVE_PASS.first_mask_advance = now;
                LIVE_PASS.first_mask_tick = tick;
                LIVE_PASS.first_mask_mcycle = mcycle;
                LIVE_PASS.first_mask_pc = pc;
            }
            if after_pass && LIVE_PASS.first_remask_tick == 0 {
                LIVE_PASS.first_remask_advance = now;
                LIVE_PASS.first_remask_tick = tick;
                LIVE_PASS.first_remask_mcycle = mcycle;
                LIVE_PASS.first_remask_pc = pc;
            }
        }
    }

    if !pnp::hid_mask_up_begin() {
        unsafe { LIVE_PASS_ARMED = false; }
        pnp::request_pause();
    }
}'''
new_finish_filter = '''pub fn live_pass_should_finish() -> bool {
    unsafe {
        if !LIVE_PASS_ARMED {
            return false;
        }
        // Fallback only.  Normal omnibus runs terminate earlier at v7.6.6 rel40.
        let finish = LIVE_PASS.first_input_advance.wrapping_add(LIVE_SAMPLE_CAP as u32 - 1);
        RNG_ADVANCE.wrapping_sub(finish) < 0x8000_0000
    }
}

fn live_pass_filter_rjoy(regs: &mut [u32]) {
    let requested = regs[0];
    if requested != RJOYP_ADDR {
        return;
    }

    unsafe {
        if !LIVE_PASS_ARMED {
            return;
        }

        LIVE_PASS.rjoy_reads = LIVE_PASS.rjoy_reads.wrapping_add(1);
        let now = RNG_ADVANCE;
        let pass_delta = now.wrapping_sub(LIVE_PASS.pass_start_advance);
        let in_pass = pass_delta < LIVE_PASS_FRAMES;
        let after_pass = now.wrapping_sub(LIVE_PASS.pass_end_advance) < 0x8000_0000;
        let pc = Gen2Reader::crystal().pc_reg();
        let tick = pnp::system_tick();
        let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
        let div = Gen2Reader::crystal().div();
        let phase4 = (((div as u16) << 6) | ((mcycle as u16) & 0x3f)) & 0x3fff;

        if in_pass {
            LIVE_PASS.passed_rjoy_reads = LIVE_PASS.passed_rjoy_reads.wrapping_add(1);
            LIVE_PASS.passthrough_rjoy_reads = LIVE_PASS.passthrough_rjoy_reads.wrapping_add(1);
            if LIVE_PASS.passed_advances == 0 || LIVE_PASS.last_pass_advance != now {
                LIVE_PASS.passed_advances = LIVE_PASS.passed_advances.saturating_add(1);
                LIVE_PASS.last_pass_advance = now;
            }
            if LIVE_PASS.first_pass_tick == 0 {
                LIVE_PASS.first_pass_advance = now;
                LIVE_PASS.first_pass_tick = tick;
                LIVE_PASS.first_pass_mcycle = mcycle;
                LIVE_PASS.first_pass_pc = pc;
                LIVE_PASS.first_pass_direct_div = div;
                LIVE_PASS.first_pass_phase4 = phase4;
            }
        } else {
            LIVE_PASS.masked_rjoy_reads = LIVE_PASS.masked_rjoy_reads.wrapping_add(1);
            if LIVE_PASS.masked_advances == 0 || LIVE_PASS.last_mask_advance != now {
                LIVE_PASS.masked_advances = LIVE_PASS.masked_advances.saturating_add(1);
                LIVE_PASS.last_mask_advance = now;
            }
            if LIVE_PASS.first_mask_tick == 0 || (after_pass && LIVE_PASS.first_remask_tick == 0) {
                if LIVE_PASS.first_mask_tick == 0 {
                    LIVE_PASS.first_mask_advance = now;
                    LIVE_PASS.first_mask_tick = tick;
                    LIVE_PASS.first_mask_mcycle = mcycle;
                    LIVE_PASS.first_mask_pc = pc;
                }
                if after_pass && LIVE_PASS.first_remask_tick == 0 {
                    LIVE_PASS.first_remask_advance = now;
                    LIVE_PASS.first_remask_tick = tick;
                    LIVE_PASS.first_remask_mcycle = mcycle;
                    LIVE_PASS.first_remask_pc = pc;
                }
            }

            if LIVE_PASS.neutral_ok != 0 {
                regs[0] = LIVE_PASS.neutral_addr as u32;
                LIVE_PASS.redirected_rjoy_reads = LIVE_PASS.redirected_rjoy_reads.wrapping_add(1);
            } else {
                LIVE_PASS_ARMED = false;
                pnp::request_pause();
                return;
            }
        }

        let i = LIVE_RJOYP_EVENT_COUNT;
        if i < LIVE_RJOYP_EVENT_CAP {
            let mode = if in_pass { 1 } else if after_pass { 2 } else { 0 };
            LIVE_RJOYP_EVENTS[i] = RJoyEvent {
                rel_advance: now.wrapping_sub(LIVE_PASS.first_input_advance) as u8,
                mode,
                redirected: (regs[0] != requested) as u8,
                requested: requested as u16,
                effective: regs[0] as u16,
                host_keys: pnp::current_keys(),
                tick,
                mcycle,
                div,
                phase4,
                gb_pc: pc,
                r1: regs[1], r2: regs[2], r3: regs[3], r4: regs[4],
                r12: regs[12], lr: regs[13], host_pc: regs[14],
            };
            LIVE_RJOYP_EVENT_COUNT += 1;
        }
    }
}'''
h = rep(h, old_finish_filter, new_finish_filter, 'finish/filter architecture')

h = rep(h,
'''fn gb_read_mem(regs: &[u32], _stack_pointer: *mut u32) {
    // Restore the exact HID word from the previous temporarily masked rJOYP
    // read before handling this GB read. Then, if this read itself is rJOYP,
    // optionally mask UP immediately before returning to the original reader.
    live_pass_restore_previous_mask();
    let requested = regs[0];
    live_pass_filter_rjoy(requested);''',
'''fn gb_read_mem(regs: &mut [u32], _stack_pointer: *mut u32) {
    // Keep the original requested address for DIV tracking. v7.6.8 may change
    // only r0 for FF00 so the original reader sees a neutral fixed-ROM byte.
    let requested = regs[0];
    live_pass_filter_rjoy(regs);''',
'gb read mutable redirect')
H.write_text(h)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

t = rep(t,
'use super::hook::{live_pass_observe_joymap, live_pass_should_finish, live_pass_telemetry};',
'use super::hook::{live_pass_observe_joymap, live_pass_rjoy_event, live_pass_rjoy_event_count, live_pass_should_finish, live_pass_telemetry};',
'trace imports')

t = rep(t,
'''        // v7.6.7 stops only after the 2F pass and four remasked frames.
        // The live HID filter remains armed until the host freeze takes effect.
        if self.probe_session && live_pass_should_finish() {
            self.stop();
            self.save();
            pnp::request_pause();
            return;
        }''',
'''        // v7.6.8 normally continues to the existing v7.6.6 rel40 gate so the
        // same run yields input proof + POST/J + actual rel40 State/DIV.
        // This is only a 48-advance fallback if rel40 classification cannot end it.
        if self.probe_session && live_pass_should_finish() {
            self.stop();
            self.save();
            pnp::request_pause();
            return;
        }''',
'finish comment')

t = t.replace('LIVEPASS,V767G,', 'LIVEPASS,V768,')
t = t.replace('LIVEPASSHOST,V767G,', 'LIVEPASSHOST,V768,')
t = t.replace('JOYMAP,V767G,', 'JOYMAP,V768,')
t = t.replace('JOYFRAME,V767G,', 'JOYFRAME,V768,')

t = rep(t,
'''game_first_mask_hjoy,game_first_pass_hjoy,game_first_remask_hjoy\nLIVEPASS,V768,''',
'''game_first_mask_hjoy,game_first_pass_hjoy,game_first_remask_hjoy,neutral_addr,neutral_value,neutral_ok,redirected_rjoy_reads,passthrough_rjoy_reads\nLIVEPASS,V768,''',
'livepass header extra')

t = rep(t,
'''{},{},{},{},{},{},{},{:02X},{:02X},{:02X}\n",''',
'''{},{},{},{},{},{},{},{:02X},{:02X},{:02X},{:04X},{:02X},{},{},{}\n",''',
'livepass format extra')

t = rep(t,
'''            lp.game_first_mask_hjoy,
            lp.game_first_pass_hjoy,
            lp.game_first_remask_hjoy
        );''',
'''            lp.game_first_mask_hjoy,
            lp.game_first_pass_hjoy,
            lp.game_first_remask_hjoy,
            lp.neutral_addr,
            lp.neutral_value,
            lp.neutral_ok,
            lp.redirected_rjoy_reads,
            lp.passthrough_rjoy_reads
        );''',
'livepass args extra')

t = rep(t, 'for i in 0..n.min(22) {', 'for i in 0..n.min(48) {', 'joy sample export cap')

t = rep(t,
'''        pnp::trace_file_close();
        set_vblank_context_capture(true);''',
'''        line.clear();
        let _ = write!(
            line,
            "\nomnibus,version,neutral_addr,neutral_value,neutral_ok,rjoy_events,redirected_reads,passthrough_reads,game_pre_obs,game_pre_up,game_pass_obs,game_pass_up,game_post4_obs,game_post4_up,first_pass_phase4,state40,div40,post_proto,post_rot,post_score,gate_models,gate_eval,gate_shiny,miss\nOMNI,V768,{:04X},{:02X},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{},{},{},{},{},{},{},{}\n",
            lp.neutral_addr, lp.neutral_value, lp.neutral_ok, live_pass_rjoy_event_count(),
            lp.redirected_rjoy_reads, lp.passthrough_rjoy_reads,
            lp.game_mask_observed_advances, lp.game_mask_up_advances,
            lp.game_pass_observed_advances, lp.game_pass_up_advances,
            lp.game_remask_observed_advances, lp.game_remask_up_advances,
            lp.first_pass_phase4, self.v763_rel40_state, self.v763_rel40_div,
            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},
            self.practical_post_rot, self.practical_post_score,
            self.v763_gate_models, self.v763_gate_evaluated, self.v763_gate_shiny_models, self.practical_miss
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(line, "\nrjoy_events,version,index,rel_advance,mode,redirected,requested,effective,host_keys,tick,mcycle,div,phase4,gb_pc,r1,r2,r3,r4,r12,lr,host_pc\n");
        pnp::trace_file_write(line.as_bytes());
        let en = live_pass_rjoy_event_count().min(128);
        for i in 0..en {
            if let Some(ev) = live_pass_rjoy_event(i) {
                line.clear();
                let _ = write!(
                    line,
                    "RJOYPEVENT,V768,{},{},{},{},{:04X},{:04X},{:08X},{},{:02X},{:02X},{:04X},{:04X},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X}\n",
                    i, ev.rel_advance, ev.mode, ev.redirected, ev.requested, ev.effective, ev.host_keys,
                    ev.tick, ev.mcycle, ev.div, ev.phase4, ev.gb_pc, ev.r1, ev.r2, ev.r3, ev.r4, ev.r12, ev.lr, ev.host_pc
                );
                pnp::trace_file_write(line.as_bytes());
            }
        }

        pnp::trace_file_close();
        set_vblank_context_capture(true);''',
'omnibus/event export')
T.write_text(t)

print('Applied v7.6.8 omnibus: ROM0-neutral rJOYP redirect + 48-ADV joy/input telemetry + rel40 continuation')
