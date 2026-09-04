from pathlib import Path

# v7.6.7: measure the actual landing jitter of a physical-UP mask -> 2-frame
# pass -> mask transition while the VC is continuously running.  This is a
# diagnostic build only: no shiny search and no RNG/DIV/DV/save mutation.

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

anchor = '''static mut ATICKS: u64 = 0;\nstatic mut STICKS: u64 = 0;\n'''
insert = r'''static mut ATICKS: u64 = 0;
static mut STICKS: u64 = 0;

// ---- v7.6.7 continuous physical-UP pass probe ---------------------------
// The existing JP Crystal hook at 0x1AF11C is a pre-dispatch hook for *all*
// GB memory reads.  During the mask window, reads of Crystal's hJoy* bytes are
// redirected to an HRAM byte that was verified to contain zero while paused.
// Nothing is written to GB RAM: the physical UP is simply hidden from game
// logic until the two-frame pass window.
const LIVE_PASS_DELAY_FRAMES: u32 = 16;
const LIVE_PASS_WIDTH_FRAMES: u32 = 2;
const LIVE_PASS_POST_FRAMES: u32 = 4;
const JOY_HRAM_FIRST: u32 = 0xff98;
const JOY_HRAM_LAST: u32 = 0xff9f;
const HRAM_GB_BASE: u32 = 0xff80;

#[derive(Clone, Copy)]
pub struct LivePassTelemetry {
    pub armed_advance: u32,
    pub delay_frames: u32,
    pub width_frames: u32,
    pub pass_start_advance: u32,
    pub pass_end_advance: u32,
    pub zero_addr: u16,
    pub zero_ok: u8,
    pub joy_reads: u32,
    pub masked_reads: u32,
    pub passed_reads: u32,
    pub first_mask_advance: u32,
    pub first_mask_tick: u64,
    pub first_mask_mcycle: u8,
    pub first_pass_advance: u32,
    pub first_pass_tick: u64,
    pub first_pass_mcycle: u8,
    pub first_pass_div: u16,
    pub first_pass_ap4: u16,
    pub first_pass_sp4: u16,
    pub first_remask_advance: u32,
    pub first_remask_tick: u64,
    pub first_remask_mcycle: u8,
}

impl LivePassTelemetry {
    const EMPTY: Self = Self {
        armed_advance: 0,
        delay_frames: LIVE_PASS_DELAY_FRAMES,
        width_frames: LIVE_PASS_WIDTH_FRAMES,
        pass_start_advance: 0,
        pass_end_advance: 0,
        zero_addr: 0,
        zero_ok: 0,
        joy_reads: 0,
        masked_reads: 0,
        passed_reads: 0,
        first_mask_advance: 0,
        first_mask_tick: 0,
        first_mask_mcycle: 0,
        first_pass_advance: 0,
        first_pass_tick: 0,
        first_pass_mcycle: 0,
        first_pass_div: 0,
        first_pass_ap4: 0,
        first_pass_sp4: 0,
        first_remask_advance: 0,
        first_remask_tick: 0,
        first_remask_mcycle: 0,
    };
}

static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;

fn find_zero_hram_addr() -> u16 {
    let base = pnp::read::<u32>(CRYSTAL_HRAM_PTR);
    if base == 0 || !pnp::is_memory_mapped(base) {
        return 0;
    }
    // hUnusedByte (FF97) is preferred.  The release/joy bytes are safe
    // fallbacks only if their current backing value is actually zero.
    for gb in [0xff97u16, 0xff9cu16, 0xff98u16] {
        let host = base.wrapping_add((gb as u32).wrapping_sub(HRAM_GB_BASE));
        if pnp::is_memory_mapped(host) && pnp::read::<u8>(host) == 0 {
            return gb;
        }
    }
    0
}

pub fn arm_live_pass_probe() {
    let base = rng_advance();
    let zero = find_zero_hram_addr();
    unsafe {
        LIVE_PASS = LivePassTelemetry {
            armed_advance: base,
            delay_frames: LIVE_PASS_DELAY_FRAMES,
            width_frames: LIVE_PASS_WIDTH_FRAMES,
            pass_start_advance: base.wrapping_add(LIVE_PASS_DELAY_FRAMES),
            pass_end_advance: base
                .wrapping_add(LIVE_PASS_DELAY_FRAMES)
                .wrapping_add(LIVE_PASS_WIDTH_FRAMES),
            zero_addr: zero,
            zero_ok: (zero != 0) as u8,
            ..LivePassTelemetry::EMPTY
        };
        LIVE_PASS_ARMED = true;
    }
}

pub fn live_pass_telemetry() -> LivePassTelemetry {
    unsafe { LIVE_PASS }
}

pub fn live_pass_should_finish() -> bool {
    unsafe {
        if !LIVE_PASS_ARMED {
            return false;
        }
        let finish = LIVE_PASS.pass_end_advance.wrapping_add(LIVE_PASS_POST_FRAMES);
        RNG_ADVANCE.wrapping_sub(finish) < 0x8000_0000
    }
}

fn live_pass_filter_read(regs: &mut [u32], requested: u32) {
    if !(JOY_HRAM_FIRST..=JOY_HRAM_LAST).contains(&requested) {
        return;
    }

    unsafe {
        if !LIVE_PASS_ARMED {
            return;
        }

        LIVE_PASS.joy_reads = LIVE_PASS.joy_reads.wrapping_add(1);
        let now = RNG_ADVANCE;
        let pass_delta = now.wrapping_sub(LIVE_PASS.pass_start_advance);
        let in_pass = pass_delta < LIVE_PASS_WIDTH_FRAMES;

        if in_pass {
            LIVE_PASS.passed_reads = LIVE_PASS.passed_reads.wrapping_add(1);
            if LIVE_PASS.first_pass_tick == 0 {
                let tick = pnp::system_tick();
                let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
                let div = ((ADIV as u16) << 8) | SDIV as u16;
                LIVE_PASS.first_pass_advance = now;
                LIVE_PASS.first_pass_tick = tick;
                LIVE_PASS.first_pass_mcycle = mcycle;
                LIVE_PASS.first_pass_div = div;
                LIVE_PASS.first_pass_ap4 = (((ADIV as u16) << 6) | ASUB as u16) & 0x3fff;
                LIVE_PASS.first_pass_sp4 = (((SDIV as u16) << 6) | SSUB as u16) & 0x3fff;
            }
            return;
        }

        LIVE_PASS.masked_reads = LIVE_PASS.masked_reads.wrapping_add(1);
        let mcycle_needed = LIVE_PASS.first_mask_tick == 0
            || (now.wrapping_sub(LIVE_PASS.pass_end_advance) < 0x8000_0000
                && LIVE_PASS.first_remask_tick == 0);
        let mut tick = 0u64;
        let mut mcycle = 0u8;
        if mcycle_needed {
            tick = pnp::system_tick();
            mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);
        }
        if LIVE_PASS.first_mask_tick == 0 {
            LIVE_PASS.first_mask_advance = now;
            LIVE_PASS.first_mask_tick = tick;
            LIVE_PASS.first_mask_mcycle = mcycle;
        }
        if now.wrapping_sub(LIVE_PASS.pass_end_advance) < 0x8000_0000
            && LIVE_PASS.first_remask_tick == 0
        {
            LIVE_PASS.first_remask_advance = now;
            LIVE_PASS.first_remask_tick = tick;
            LIVE_PASS.first_remask_mcycle = mcycle;
        }

        if LIVE_PASS.zero_addr != 0 {
            // Redirect only the read address.  The GB HRAM contents, RNG, DIV,
            // DVs and save are never modified by this probe.
            regs[0] = LIVE_PASS.zero_addr as u32;
        } else {
            LIVE_PASS.zero_ok = 0;
        }
    }
}
'''
if anchor not in h:
    raise SystemExit('v767 hook telemetry anchor missing')
h = h.replace(anchor, insert, 1)

old = '''fn gb_read_mem(regs: &[u32], _stack_pointer: *mut u32) {\n    unsafe { ANY_HITS = ANY_HITS.wrapping_add(1) };\n\n    if regs[0] != 0xff04 {\n        return;\n    }\n'''
new = '''fn gb_read_mem(regs: &mut [u32], _stack_pointer: *mut u32) {\n    unsafe { ANY_HITS = ANY_HITS.wrapping_add(1) };\n\n    // Preserve the requested GB address for diagnostics/DIV handling.  The\n    // live-pass filter may replace regs[0] only for hJoy* reads before the\n    // original VC memory-read routine executes.\n    let requested = regs[0];\n    live_pass_filter_read(regs, requested);\n\n    if requested != 0xff04 {\n        return;\n    }\n'''
if old not in h:
    raise SystemExit('v767 gb_read_mem anchor missing')
h = h.replace(old, new, 1)
H.write_text(h)

# Re-export the live-pass armer from crystal.
M = Path('reader_core/src/crystal/mod.rs')
m = M.read_text()
old = 'pub use hook::init_crystal;'
new = 'pub use hook::{arm_live_pass_probe, init_crystal};'
if old not in m:
    raise SystemExit('v767 crystal mod anchor missing')
m = m.replace(old, new, 1)
M.write_text(m)

# Export a C ABI entry point so the pause loop can arm both Trace and live pass
# on the same frozen root.
L = Path('reader_core/src/lib.rs')
l = L.read_text()
anchor = '''#[no_mangle]\npub extern "C" fn run_frame() {\n'''
insert = '''#[no_mangle]\npub extern "C" fn arm_suicune_live_pass() {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        crystal::arm_live_pass_probe();\n    }\n}\n\n#[no_mangle]\npub extern "C" fn run_frame() {\n'''
if anchor not in l:
    raise SystemExit('v767 lib export anchor missing')
l = l.replace(anchor, insert, 1)
L.write_text(l)

# C header + pause-loop control. Y+X arms the ordinary Suicune trace and the
# live-pass filter together. Once the operator has released Y+X and only
# physical UP remains held, the game resumes automatically; R is not used.
P = Path('3gx/includes/pokereader.h')
p = P.read_text()
if 'void arm_suicune_live_pass();' not in p:
    p = p.replace('void arm_suicune_probe();', 'void arm_suicune_probe();\nvoid arm_suicune_live_pass();')
P.write_text(p)

C = Path('3gx/sources/main.c')
c = C.read_text()
anchor = 'static u32 fixed_run_id = 0;\n'
if anchor not in c:
    raise SystemExit('v767 C state anchor missing')
c = c.replace(anchor, anchor + 'static bool live_pass_pending = false;\n', 1)

old = '''            if (just_pressed & KEY_X)\n            {\n                arm_suicune_probe();\n            }\n'''
new = '''            if (just_pressed & KEY_X)\n            {\n                arm_suicune_probe();\n                arm_suicune_live_pass();\n                live_pass_pending = true;\n                // v7.6.7 does not use the old paused Exact2F runner.\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                fixed_armed = false;\n                continue;\n            }\n'''
if old not in c:
    raise SystemExit('v767 Y+X anchor missing')
c = c.replace(old, new, 1)

anchor = '''        if (fixed_run_pending)\n        {\n'''
insert = '''        // v7.6.7 staging: do not resume until the operator has released the\n        // Y+X arming chord and physical UP is the *only* held key.  From this\n        // point the VC runs continuously; the Rust GB-read hook masks UP for\n        // 16 advances, passes it for 2, then masks it again.\n        if (live_pass_pending)\n        {\n            if (held == KEY_DUP)\n            {\n                live_pass_pending = false;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(10000000);\n            continue;\n        }\n\n        if (fixed_run_pending)\n        {\n'''
if anchor not in c:
    raise SystemExit('v767 pending anchor missing')
c = c.replace(anchor, insert, 1)
C.write_text(c)

# Trace: auto-stop/save a few frames after the two-frame pass, and append a
# compact telemetry row. This build intentionally stops before rel40: first we
# prove that mask->pass itself is real and measure its phase width.
T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
use_anchor = 'use super::reader::Gen2Reader;\n'
if use_anchor not in t:
    raise SystemExit('v767 trace import anchor missing')
t = t.replace(
    use_anchor,
    'use super::hook::{live_pass_should_finish, live_pass_telemetry};\n' + use_anchor,
    1,
)

anchor = '''        self.len += 1;\n\n        if self.probe_active && window[2] == SUICUNE_SPECIES {\n'''
insert = '''        self.len += 1;\n\n        // Stop soon after the live two-frame window.  The mask stays active\n        // until the host freeze takes effect, so a still-held physical UP\n        // cannot leak extra game frames while the CSV is being finalized.\n        if self.probe_session && live_pass_should_finish() {\n            self.stop();\n            self.save();\n            pnp::request_pause();\n            return;\n        }\n\n        if self.probe_active && window[2] == SUICUNE_SPECIES {\n'''
if anchor not in t:
    raise SystemExit('v767 trace auto-stop anchor missing')
t = t.replace(anchor, insert, 1)

old_close = '''        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();\n'''
pos = t.rfind(old_close)
if pos < 0:
    raise SystemExit('v767 CSV close anchor missing')
new_close = r'''        pnp::trace_file_write(line.as_bytes());

        let lp = live_pass_telemetry();
        line.clear();
        let _ = write!(
            line,
            "\nlive_pass,version,armed_advance,delay_frames,width_frames,pass_start_advance,pass_end_advance,zero_addr,zero_ok,joy_reads,masked_reads,passed_reads,first_mask_advance,first_mask_tick,first_mask_mcycle,first_pass_advance,first_pass_tick,first_pass_mcycle,first_pass_div,first_pass_ap4,first_pass_sp4,first_remask_advance,first_remask_tick,first_remask_mcycle\nLIVEPASS,V767,{},{},{},{},{},{:04X},{},{},{},{},{},{},{:02X},{},{},{:02X},{:04X},{:04X},{:04X},{},{},{:02X}\n",
            lp.armed_advance,
            lp.delay_frames,
            lp.width_frames,
            lp.pass_start_advance,
            lp.pass_end_advance,
            lp.zero_addr,
            lp.zero_ok,
            lp.joy_reads,
            lp.masked_reads,
            lp.passed_reads,
            lp.first_mask_advance,
            lp.first_mask_tick,
            lp.first_mask_mcycle,
            lp.first_pass_advance,
            lp.first_pass_tick,
            lp.first_pass_mcycle,
            lp.first_pass_div,
            lp.first_pass_ap4,
            lp.first_pass_sp4,
            lp.first_remask_advance,
            lp.first_remask_tick,
            lp.first_remask_mcycle
        );
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();
'''
t = t[:pos] + t[pos:].replace(old_close, new_close, 1)

# Make the post-save state obvious on the RNG page.
old_ui = '''        } else if self.probe_session {\n            pnp::println!("Probe STOP T{}", self.probe_target.advance);\n            pnp::println!("NO RESULT D{}", deep_log_count());\n            pnp::println!(\n                "TSub {:02X}/{:02X} B{}",\n                self.probe_target.asub,\n                self.probe_target.ssub,\n                self.probe_target.asub >> 3\n            );\n'''
new_ui = '''        } else if self.probe_session {\n            let lp = live_pass_telemetry();\n            pnp::println!("V767 LIVE PASS SAVED");\n            pnp::println!("J{} M{} P{} Z{}",lp.joy_reads,lp.masked_reads,lp.passed_reads,lp.zero_ok);\n            pnp::println!("A{} F{:02X}",lp.first_pass_advance,lp.first_pass_mcycle);\n'''
if old_ui not in t:
    raise SystemExit('v767 UI anchor missing')
t = t.replace(old_ui, new_ui, 1)
T.write_text(t)

print('Applied v7.6.7 live physical-UP mask -> 2F pass -> mask jitter probe')
