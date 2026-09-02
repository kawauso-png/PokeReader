#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
trace_path = Path('reader_core/src/crystal/trace.rs')
frame_path = Path('reader_core/src/crystal/frame.rs')
lib_path = Path('reader_core/src/lib.rs')
header_path = Path('3gx/includes/pokereader.h')

m = main_path.read_text()
t = trace_path.read_text()
f = frame_path.read_text()
l = lib_path.read_text()
h = header_path.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v732 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# -------------------------------------------------------------------------
# 1) Live scan: an A epoch no longer waits specifically for r10 before asking
#    the host to pause.  The request->bottom-freeze transport was observed to
#    move 72/122+ RNG advances, so the requested r10 is not the root actually
#    used by UP+B.  Pause on the first exact A cell and lock the *frozen* root
#    afterward instead.
# -------------------------------------------------------------------------
old = '''        if rot != 10 { return; }\n\n        self.phase_target_count = self.phase_target_count.saturating_add(1);\n        self.phase_target_proto = proto0; self.phase_target_rot = rot;\n        self.practical_live_found_advance = cur;\n        self.practical_live_found_state = reader.rng_state();\n        self.practical_live_found_div = measured_div();\n        self.practical_live_found_lane = 253; // A/r10 control probe\n        self.practical_live_found_tick = pnp::system_tick();\n        self.practical_live_found_ai = 0; self.practical_live_found_si = 0;\n        self.practical_live_scan = false; self.practical_scan_enabled = false;\n        pre_vblank_timing_capture_stop();\n        self.practical_candidate_valid = false; self.practical_active = false;\n        pnp::request_pause();\n'''
new = '''        // v7.3.2: first exact A root is enough to enter the pause-root lock.\n        // Do not pretend the scan root survives request_pause() transport.\n        self.phase_target_count = self.phase_target_count.saturating_add(1);\n        self.phase_target_proto = proto0; self.phase_target_rot = rot;\n        self.practical_live_found_advance = cur;\n        self.practical_live_found_state = reader.rng_state();\n        self.practical_live_found_div = measured_div();\n        self.practical_live_found_lane = 253; // pause-root A/r10 lock request\n        self.practical_live_found_tick = pnp::system_tick();\n        self.practical_live_found_ai = 0; self.practical_live_found_si = 0;\n        self.practical_live_scan = false; self.practical_scan_enabled = false;\n        // Keep the separate host-timing ring alive through neutral lock steps.\n        // arm_suicune_probe() snapshots and stops it at the actual locked root.\n        self.practical_candidate_valid = false; self.practical_active = false;\n        pnp::request_pause();\n'''
t = rep(t, old, new, 'replace r10 scan gate with first-A pause')

# Stop the gated timing capture only when the actual frozen donor is armed.
old = '''        self.pre_vblank_ring = latest_pre_vblank_ring();\n        self.pre_vblank_timing_ring = latest_pre_vblank_timing_ring();\n        self.probe_target = ProbeTarget {'''
new = '''        self.pre_vblank_ring = latest_pre_vblank_ring();\n        self.pre_vblank_timing_ring = latest_pre_vblank_timing_ring();\n        pre_vblank_timing_capture_stop();\n        self.probe_target = ProbeTarget {'''
t = rep(t, old, new, 'stop timing ring at actual arm')

# -------------------------------------------------------------------------
# 2) Rust-side frozen-root classifier.  It deliberately uses the exact same
#    17-VBlank classify_pre_ring() path later written as PREFP, so READY means
#    the future CSV authoritative PRE really is A/r10.
#
# Packed return:
# bit31 = v7.3.x control pause requested (lane 253)
# bit30 = non-A epoch / RESET sentinel (lane 254)
# bit29 = full17 + consecutive + best_score==0
# bits 8..11 = rot, bits 0..7 = proto byte
# -------------------------------------------------------------------------
anchor = '''    pub fn status_line(&self) -> (&'static str, u32, usize) {'''
method = '''    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {\n        let mut out = 0u32;\n        if self.practical_live_found_lane == 253 && !self.probe_session { out |= 1u32 << 31; }\n        if self.practical_live_found_lane == 254 && !self.probe_session { out |= 1u32 << 30; }\n\n        let r = latest_pre_vblank_ring();\n        let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);\n        let (proto, rot, best, second, consecutive) = classify_pre_ring(&r);\n        self.phase_now_proto = proto;\n        self.phase_now_rot = rot;\n        self.phase_best_score = best;\n        self.phase_second_score = second;\n        self.phase_consecutive = consecutive;\n\n        if count == PRE_VBLANK_RING_LEN && consecutive && best == 0 {\n            out |= 1u32 << 29;\n            out |= proto as u32;\n            out |= (rot as u32) << 8;\n\n            // Make PHASESCAN's found/target fields follow the root that is\n            // actually frozen, not the earlier request_pause() root.\n            if self.practical_live_found_lane == 253 && !self.probe_session {\n                self.phase_target_proto = proto;\n                self.phase_target_rot = rot;\n                self.practical_live_found_advance = rng_advance();\n                self.practical_live_found_state = reader.rng_state();\n                self.practical_live_found_div = measured_div();\n                self.practical_live_found_tick = pnp::system_tick();\n            }\n        }\n        out\n    }\n\n'''
if t.count(anchor) != 1:
    raise SystemExit(f'v732 status_line anchor count {t.count(anchor)}')
t = t.replace(anchor, method + anchor, 1)

# Frame wrapper called directly from the C freeze loop.
anchor = '''pub fn search_suicune_practical_targets() {\n    let reader = Gen2Reader::crystal();\n    let state = unsafe { get_state() };\n    state.trace.start_practical_scan(&reader);\n}\n'''
insert = anchor + '''\n/// Called from the C bottom-screen freeze loop while the VC is frozen.\n/// Returns the authoritative current 17-VBlank PRE cell used by PREFP.\npub fn suicune_control_pause_cell() -> u32 {\n    let reader = Gen2Reader::crystal();\n    let state = unsafe { get_state() };\n    state.trace.control_pause_cell(&reader)\n}\n'''
f = rep(f, anchor, insert, 'frame pause-cell wrapper')

# C ABI export.
anchor = '''#[no_mangle]\npub extern "C" fn arm_suicune_probe() {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        crystal::arm_suicune_probe();\n    }\n}\n'''
insert = anchor + '''\n#[no_mangle]\npub extern "C" fn suicune_control_pause_cell() -> u32 {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        crystal::suicune_control_pause_cell()\n    } else {\n        0\n    }\n}\n'''
l = rep(l, anchor, insert, 'lib C ABI export')

if 'u32 suicune_control_pause_cell();' not in h:
    h = rep(h, 'void arm_suicune_probe();', 'void arm_suicune_probe();\nu32 suicune_control_pause_cell();', 'header declaration')

# -------------------------------------------------------------------------
# 3) C pause-root lock.  Once the bottom-screen freeze really exists, classify
#    the frozen ring.  If it is not A/r10, release exactly one neutral display
#    frame by breaking the freeze loop with is_paused still true.  The next
#    bottom hook freezes again and rechecks.  No HID injection is used.
# -------------------------------------------------------------------------
slot_decl = '''static u32 suicune_phase_slot = 1;'''
root_decl = '''static u32 suicune_phase_slot = 1;\n\n// v7.3.2 PauseRootLock. request_pause() is asynchronous with respect to the\n// bottom-screen freeze hook, so the scanned PRE is not necessarily the root\n// from which Exact-2F starts.  Neutral one-frame stepping continues only while\n// every physical key is released, then stops on authoritative PREFP A/r10.\nstatic bool suicune_root_lock_active = false;\nstatic bool suicune_root_lock_ready = false;\nstatic bool suicune_root_lock_failed = false;\nstatic u32 suicune_root_lock_steps = 0;\nstatic u32 suicune_root_lock_last_cell = 0;\n#define SUICUNE_ROOT_LOCK_MAX_STEPS 64U'''
m = rep(m, slot_decl, root_decl, 'root lock state declarations')

# Insert before fixed_run_pending handling, after the earlier special freeze
# modes.  This keeps Exact-2F behavior untouched once the donor is armed.
anchor = '''        // Y+L schedules a fixed run, but do not let a game frame through while\n        // either trigger modifier is still physically held.  This avoids the\n'''
block = '''        // v7.3.2 authoritative frozen-root lock.  The Rust helper classifies\n        // the same ring that PREFP later saves.  A neutral `break` releases one\n        // display frame only; is_paused remains true, so the next bottom hook\n        // freezes again before another frame can free-run.\n        if (!suicune_auto_resume_pending && !fixed_run_pending && fixed_frames_remaining == 0)\n        {\n            u32 cell = suicune_control_pause_cell();\n            bool requested = (cell & 0x80000000U) != 0;\n            bool valid = (cell & 0x20000000U) != 0;\n            u32 proto = cell & 0xffU;\n            u32 rot = (cell >> 8) & 0x0fU;\n            suicune_root_lock_last_cell = cell;\n\n            if (requested && !suicune_root_lock_ready && !suicune_root_lock_failed)\n                suicune_root_lock_active = true;\n\n            if (suicune_root_lock_active && !suicune_root_lock_ready)\n            {\n                if (valid && proto == (u32)'A' && rot == 10U)\n                {\n                    suicune_root_lock_ready = true;\n                    suicune_root_lock_active = false;\n                    continue;\n                }\n\n                if (suicune_root_lock_steps >= SUICUNE_ROOT_LOCK_MAX_STEPS)\n                {\n                    suicune_root_lock_failed = true;\n                    suicune_root_lock_active = false;\n                    continue;\n                }\n\n                const u32 lock_block_keys = KEY_A | KEY_B | KEY_X | KEY_Y |\n                    KEY_DUP | KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT |\n                    KEY_L | KEY_R | KEY_START | KEY_SELECT;\n                if ((held & lock_block_keys) != 0)\n                {\n                    svcSleepThread(1000000);\n                    continue;\n                }\n\n                suicune_root_lock_steps++;\n                break; // exactly one neutral frame; stay logically paused\n            }\n        }\n\n'''
if m.count(anchor) != 1:
    raise SystemExit(f'v732 pause insertion anchor count {m.count(anchor)}')
m = m.replace(anchor, block + anchor, 1)

# Slot selection and UP+B are legal only after the frozen root is really A/r10.
old = '''        if ((just_pressed & KEY_X) && !(held & KEY_Y)\n            && !fixed_run_pending && !suicune_auto_resume_pending)'''
new = '''        if ((just_pressed & KEY_X) && !(held & KEY_Y)\n            && suicune_root_lock_ready\n            && !fixed_run_pending && !suicune_auto_resume_pending)'''
m = rep(m, old, new, 'gate slot toggle on locked root')

old = '''        if ((held & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)\n            && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n                arm_suicune_probe();'''
new = '''        if ((held & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)\n            && suicune_root_lock_ready\n            && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n                // Consume the lock before arming so no neutral lock step can\n                // interleave with Exact-2F.\n                suicune_root_lock_ready = false;\n                suicune_root_lock_active = false;\n                arm_suicune_probe();'''
m = rep(m, old, new, 'gate UP+B on locked root')

# Every fresh Y+DOWN scan clears prior lock state.
old = '''            if (just_pressed & KEY_DDOWN)\n            {\n                search_suicune_practical_targets();'''
new = '''            if (just_pressed & KEY_DDOWN)\n            {\n                suicune_root_lock_active = false;\n                suicune_root_lock_ready = false;\n                suicune_root_lock_failed = false;\n                suicune_root_lock_steps = 0;\n                suicune_root_lock_last_cell = 0;\n                search_suicune_practical_targets();'''
m = rep(m, old, new, 'reset lock on Y+DOWN')

# Manual resume also clears stale control state.
old = '''            is_paused = false;\n            fixed_frames_remaining = 0;\n            fixed_run_pending = false;\n            suicune_auto_resume_pending = false;\n            suicune_phase_lock_active = false;\n            break;'''
new = '''            is_paused = false;\n            fixed_frames_remaining = 0;\n            fixed_run_pending = false;\n            suicune_auto_resume_pending = false;\n            suicune_phase_lock_active = false;\n            suicune_root_lock_active = false;\n            suicune_root_lock_ready = false;\n            suicune_root_lock_failed = false;\n            break;'''
m = rep(m, old, new, 'clear lock on manual resume')

# -------------------------------------------------------------------------
# 4) UI: display the *live latest ring* during neutral stepping.  Because the
#    top-screen draw happens after each released lock frame, the final frozen
#    screen visibly says A/r10 LOCKED before the user supplies UP+B.
# -------------------------------------------------------------------------
old = '''        if self.practical_scan_enabled {\n            pnp::println!("S730 A10 CONTROL");\n            if self.phase_now_proto == b'?' { pnp::println!("NOW ?"); }\n            else { pnp::println!("NOW {}/r{} L{} S{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag, self.phase_best_score); }\n            pnp::println!("FR{} EX{}", self.practical_live_checked, self.phase_exact_count);\n            pnp::println!("A EPOCH -> A/r10");\n        } else if self.practical_live_found_lane == 254 && !self.probe_session {\n            pnp::println!("S730 NEED A EPOCH");\n            pnp::println!("GOT {}/r{}", self.phase_target_proto as char, self.phase_target_rot);\n            pnp::println!("RESET VC");\n        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            pnp::println!("S730 A/r10 READY");\n            pnp::println!("ABS SLOT{} X=TOGGLE", pnp::fixed_a_frame().phase_slot & 7);\n            pnp::println!("UP+B RUN");\n'''
new = '''        if self.practical_scan_enabled {\n            pnp::println!("S732 ROOTLOCK SCAN");\n            if self.phase_now_proto == b'?' { pnp::println!("NOW ?"); }\n            else { pnp::println!("NOW {}/r{} L{} S{}", self.phase_now_proto as char, self.phase_now_rot, self.phase_now_lag, self.phase_best_score); }\n            pnp::println!("FR{} EX{}", self.practical_live_checked, self.phase_exact_count);\n            pnp::println!("A EPOCH -> AUTOLOCK");\n        } else if self.practical_live_found_lane == 254 && !self.probe_session {\n            pnp::println!("S732 NEED A EPOCH");\n            pnp::println!("GOT {}/r{}", self.phase_target_proto as char, self.phase_target_rot);\n            pnp::println!("RESET VC");\n        } else if self.practical_live_found_lane == 253 && !self.probe_session {\n            let r = latest_pre_vblank_ring();\n            let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);\n            let (lp, lr, lb, _, lc) = classify_pre_ring(&r);\n            let locked = count == PRE_VBLANK_RING_LEN && lc && lb == 0 && lp == b'A' && lr == 10;\n            if locked {\n                pnp::println!("S732 A/r10 LOCKED");\n                pnp::println!("ABS SLOT{} X=TOGGLE", pnp::fixed_a_frame().phase_slot & 7);\n                pnp::println!("UP+B RUN");\n            } else {\n                if count == PRE_VBLANK_RING_LEN && lc { pnp::println!("S732 LOCK {}/r{} S{}", lp as char, lr, lb); }\n                else { pnp::println!("S732 ROOT LOCK"); }\n                pnp::println!("AUTO NEUTRAL 1F");\n                pnp::println!("WAIT - NO INPUT");\n            }\n'''
t = rep(t, old, new, 'v732 root-lock UI')

t = t.replace('S730 CONTROL RUN', 'S732 CONTROL RUN').replace('S730 IDLE', 'S732 IDLE')
t = t.replace('PHASESCAN,V730', 'PHASESCAN,V732').replace('PRECOUNT,V730', 'PRECOUNT,V732')

main_path.write_text(m)
trace_path.write_text(t)
frame_path.write_text(f)
lib_path.write_text(l)
header_path.write_text(h)
print('Applied Suicune v7.3.2 PauseRootLock: frozen PREFP A/r10 before slot-controlled Exact-2F')
