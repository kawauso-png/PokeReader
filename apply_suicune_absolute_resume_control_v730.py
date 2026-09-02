#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
trace_path = Path('reader_core/src/crystal/trace.rs')

m = main_path.read_text()
t = trace_path.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v730 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


def fspan(text, sig):
    a = text.find(sig)
    if a < 0:
        raise SystemExit('v730 missing function ' + sig)
    b = text.find('{', a)
    if b < 0:
        raise SystemExit('v730 missing opening brace ' + sig)
    d = 0
    for i in range(b, len(text)):
        if text[i] == '{':
            d += 1
        elif text[i] == '}':
            d -= 1
            if d == 0:
                return a, i + 1
    raise SystemExit('v730 unclosed function ' + sig)

# -------------------------------------------------------------------------
# 1) Exact causal experiment: A/r10 only.
#    A epochs stop on A/r10.  A non-A epoch stops immediately with RESET,
#    because the proto is stable during an epoch and waiting thousands of FR
#    cannot turn B/C/D into A.
# -------------------------------------------------------------------------
start, end = fspan(t, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)')
monitor = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled
            || !self.practical_live_scan
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        { return; }

        let cur = rng_advance();
        if cur == self.practical_live_last_advance { return; }
        self.practical_live_last_advance = cur;
        self.practical_live_checked = self.practical_live_checked.saturating_add(1);

        let r = latest_pre_vblank_ring();
        let n = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n != PRE_VBLANK_RING_LEN {
            self.phase_now_proto = b'?'; self.phase_now_lag = 0xff;
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        }
        let (last, _) = pre_ring_sample(&r, n - 1);
        let lag = cur.wrapping_sub(last);
        let (proto0, mut rot, best, second, ok) = classify_pre_ring(&r);
        self.phase_best_score = best;
        self.phase_second_score = second;
        self.phase_consecutive = ok;
        if lag > 1 || !ok {
            self.phase_now_proto = proto0;
            self.phase_now_rot = rot;
            self.phase_now_lag = lag.min(255) as u8;
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        }
        if lag == 1 { rot = rot.wrapping_add(1) & 15; }
        self.phase_now_proto = proto0;
        self.phase_now_rot = rot;
        self.phase_now_lag = lag as u8;

        // Control trials must start from the exact current PRE root.
        if lag != 0 || best != 0 { return; }
        if self.practical_live_checked < PRE_VBLANK_RING_LEN as u32 { return; }

        self.phase_exact_count = self.phase_exact_count.saturating_add(1);
        if let Some(ci) = Self::phase_cell_index(proto0, rot) {
            self.phase_counts[ci] = self.phase_counts[ci].saturating_add(1);
        }

        // One epoch keeps one prototype while rot cycles.  Reject non-A
        // immediately instead of burning 3000 FR waiting for an impossible A/r10.
        if proto0 != b'A' {
            self.phase_target_proto = proto0; self.phase_target_rot = rot;
            self.practical_live_found_advance = cur;
            self.practical_live_found_state = reader.rng_state();
            self.practical_live_found_div = measured_div();
            self.practical_live_found_lane = 254; // NEED-A sentinel
            self.practical_live_found_tick = pnp::system_tick();
            self.practical_live_found_ai = 0; self.practical_live_found_si = 0;
            self.practical_live_scan = false; self.practical_scan_enabled = false;
            pre_vblank_timing_capture_stop();
            self.practical_candidate_valid = false; self.practical_active = false;
            pnp::request_pause();
            return;
        }

        if rot != 10 { return; }

        self.phase_target_count = self.phase_target_count.saturating_add(1);
        self.phase_target_proto = proto0; self.phase_target_rot = rot;
        self.practical_live_found_advance = cur;
        self.practical_live_found_state = reader.rng_state();
        self.practical_live_found_div = measured_div();
        self.practical_live_found_lane = 253; // A/r10 control probe
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = 0; self.practical_live_found_si = 0;
        self.practical_live_scan = false; self.practical_scan_enabled = false;
        pre_vblank_timing_capture_stop();
        self.practical_candidate_valid = false; self.practical_active = false;
        pnp::request_pause();
    }'''
t = t[:start] + monitor + t[end:]

old_ui = '''        if self.practical_scan_enabled {
            pnp::println!("S723 INDEXLESS");
            if self.phase_now_proto == b'?' { pnp::println!("NOW ?"); }
            else { pnp::println!("NOW {}/r{} L{} S{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag, self.phase_best_score); }
            pnp::println!("FR{} EX{} TG{}", self.practical_live_checked, self.phase_exact_count, self.phase_target_count);
            if self.practical_live_checked < 3000 { pnp::println!("PRI A3 A10 B1 B11 D12"); }
            else { pnp::println!("FALLBACK ANY EXACT"); }
        } else if self.practical_live_found_lane == 253 && !self.probe_session {
            pnp::println!("S723 PROBE {}/r{}", self.phase_target_proto as char, self.phase_target_rot);
            pnp::println!("UP+B DONOR");
'''
new_ui = '''        if self.practical_scan_enabled {
            pnp::println!("S730 A10 CONTROL");
            if self.phase_now_proto == b'?' { pnp::println!("NOW ?"); }
            else { pnp::println!("NOW {}/r{} L{} S{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag, self.phase_best_score); }
            pnp::println!("FR{} EX{}", self.practical_live_checked, self.phase_exact_count);
            pnp::println!("A EPOCH -> A/r10");
        } else if self.practical_live_found_lane == 254 && !self.probe_session {
            pnp::println!("S730 NEED A EPOCH");
            pnp::println!("GOT {}/r{}", self.phase_target_proto as char, self.phase_target_rot);
            pnp::println!("RESET VC");
        } else if self.practical_live_found_lane == 253 && !self.probe_session {
            pnp::println!("S730 A/r10 READY");
            pnp::println!("ABS SLOT{} X=TOGGLE", fixed.phase_slot & 7);
            pnp::println!("UP+B RUN");
'''
t = rep(t, old_ui, new_ui, 'control UI')
t = t.replace('S723 PHASE RUN', 'S730 CONTROL RUN').replace('S723 IDLE', 'S730 IDLE')
t = t.replace('PHASESCAN,V723', 'PHASESCAN,V730').replace('PRECOUNT,V723', 'PRECOUNT,V730')

# -------------------------------------------------------------------------
# 2) Manipulate the variable that correlated with POST in v7.2.4 data:
#       floor(resume_command_tick / 4481233) mod 8.
#    Default slot 1; X toggles 1 <-> 6 while paused at A/r10.
# -------------------------------------------------------------------------
m = rep(m,
'''static u32 suicune_phase_slot = 0;''',
'''// v7.3 absolute resume-control slot.  Existing v4.9 telemetry fields are
// reused, but slot now means absolute floor(system_tick / period) mod 8.
// A/r10 observations: slot1 -> C/r8 (2/2), slot6 -> D/r2 (2/2).
static u32 suicune_phase_slot = 1;''',
'absolute slot default')

arm_marker = '''        // v7.2.4 robust diagnostic arm.  In auto-paused probe mode, relying
        // only on the one-poll `just_pressed` edge can miss B entirely.'''
if m.count(arm_marker) != 1:
    raise SystemExit(f'v730 robust arm marker count {m.count(arm_marker)}')
toggle = '''        // v7.3 A/r10 control selector. X is consumed inside the pause loop;
        // no VC frame is released.  Only the two experimentally supported
        // A/r10 slots are exposed in this causal validation build.
        if ((just_pressed & KEY_X) && !(held & KEY_Y)
            && !fixed_run_pending && !suicune_auto_resume_pending)
        {
            suicune_phase_slot = (suicune_phase_slot == 1) ? 6 : 1;
            continue;
        }

'''
m = m.replace(arm_marker, toggle + arm_marker, 1)

old_wait = '''                if (suicune_phase_lock_active && suicune_phase_anchor_tick != 0)
                {
                    u64 now = suicune_obs_up_release_tick;
                    u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_phase_slot) / SUICUNE_PHASE_SLOTS;
                    u64 target = suicune_phase_anchor_tick + offset;
                    if (target <= now + 4096ULL)
                    {
                        u64 delta = (now + 4096ULL) - target;
                        target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;
                    }
                    suicune_phase_target_tick = target;
                    while (svcGetSystemTick() < target) { }
                    suicune_phase_actual_tick = svcGetSystemTick();
                }'''
new_wait = '''                if (suicune_phase_lock_active)
                {
                    u64 now = suicune_obs_up_release_tick;
                    u32 wanted = suicune_phase_slot & 7U;
                    // Pick the next absolute host-period boundary whose cycle
                    // number has the requested low 3 bits.  resume_command_tick
                    // follows only a few hundred ticks later, far inside the same
                    // 4.48M-tick cycle, so it inherits this absolute slot.
                    u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;
                    while (((u32)cycle & 7U) != wanted) cycle++;
                    u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;
                    if (target <= now + 4096ULL)
                    {
                        cycle += 8ULL;
                        target = cycle * SUICUNE_PHASE_PERIOD_TICKS;
                    }
                    suicune_phase_target_tick = target;
                    while (svcGetSystemTick() < target) { }
                    suicune_phase_actual_tick = svcGetSystemTick();
                }'''
m = rep(m, old_wait, new_wait, 'absolute resume wait')

# Add an explicit row next to the existing RPH metrics.  No new timing-path
# reads are introduced; this is written only after the encounter trace stops.
anchor = '''        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();'''
control_row = '''        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let abs_actual = if rpm.period != 0 { ((rpm.actual / rpm.period) & 7) as u32 } else { 255 };
        let (exp_proto, exp_rot) = match rpm.slot & 7 {
            1 => ('C', 8u32),
            6 => ('D', 2u32),
            _ => ('?', 255u32),
        };
        let _ = write!(line,
            "\\ncontrol_resume,version,pre_proto,pre_rot,wanted_slot,actual_slot,expected_post_proto,expected_post_rot\\nCONTROL,V730,A,10,{},{},{},{}\\n",
            rpm.slot & 7, abs_actual, exp_proto, exp_rot
        );
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();'''
t = rep(t, anchor, control_row, 'CONTROL CSV row')

main_path.write_text(m)
trace_path.write_text(t)
print('Applied Suicune v7.3.0 Absolute Resume Control: A/r10 causal slot1/slot6 experiment')
