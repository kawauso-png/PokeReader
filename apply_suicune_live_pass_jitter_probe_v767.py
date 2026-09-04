from pathlib import Path

# v7.6.7 diagnostic: continuous VC execution with physical UP hidden only at
# the 3DS HID -> emulated rJOYP boundary.  No GB RAM, RNG, DIV, DV or save data
# is written.  For masked rJOYP reads, the real HID key word is saved, UP is
# temporarily cleared through the physical alias, and the exact saved word is
# restored at the next GB-read hook before any other read is handled.


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


def replace_braced_block(src, marker, new_block, label):
    a = src.find(marker)
    if a < 0:
        raise SystemExit(f'v767 {label}: marker not found')
    b = src.find('{', a)
    if b < 0:
        raise SystemExit(f'v767 {label}: opening brace not found')
    depth = 0
    end = -1
    for i in range(b, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise SystemExit(f'v767 {label}: closing brace not found')
    return src[:a] + new_block + src[end:]


# -------------------------------------------------------------------------
# C HID helper: temporarily mask physical UP in the shared HID key word.
# The ordinary VA is read-only, but PokeReader already uses an uncached
# physical alias to patch mapped process memory.  We never synthesize input:
# the exact original word is restored after each masked rJOYP read.
# -------------------------------------------------------------------------
HIDC = Path('3gx/sources/hid.c')
hc = HIDC.read_text()
hc = rep(
    hc,
    '#include <3ds.h>\n',
    '#include <3ds.h>\n#include "common.h"\n',
    'hid common include',
)
hc = rep(
    hc,
    'u32 g_previous_keys = 0;\n',
    '''u32 g_previous_keys = 0;
static bool g_up_mask_active = false;
static u32 g_up_mask_saved = 0;
static u32 g_up_mask_begin_failures = 0;
static u32 g_up_mask_restore_failures = 0;
''',
    'hid mask state',
)
hc += r'''

u32 hid_up_mask_capable()
{
  if (g_key_addr == 0)
    return 0;
  u32 pa = svcConvertVAToPA((const void *)g_key_addr, false);
  return pa != 0;
}

u32 hid_up_mask_begin()
{
  // Never stack masks. Restore the previous exact word first.
  if (g_up_mask_active)
  {
    vu32 *old_pa = (vu32 *)PA_FROM_VA_PTR(g_key_addr);
    *old_pa = g_up_mask_saved;
    g_up_mask_active = false;
  }

  if (!hid_up_mask_capable())
  {
    g_up_mask_begin_failures++;
    return 0;
  }

  vu32 *pa = (vu32 *)PA_FROM_VA_PTR(g_key_addr);
  u32 original = *g_key_addr;
  g_up_mask_saved = original;
  *pa = original & ~KEY_DUP;
  __asm__ volatile("dmb" ::: "memory");

  if ((*pa & KEY_DUP) != 0)
  {
    g_up_mask_begin_failures++;
    *pa = original;
    __asm__ volatile("dmb" ::: "memory");
    return 0;
  }

  g_up_mask_active = true;
  return 1;
}

u32 hid_up_mask_restore()
{
  if (!g_up_mask_active)
    return 1;
  if (g_key_addr == 0)
  {
    g_up_mask_restore_failures++;
    g_up_mask_active = false;
    return 0;
  }

  vu32 *pa = (vu32 *)PA_FROM_VA_PTR(g_key_addr);
  u32 saved = g_up_mask_saved;
  *pa = saved;
  __asm__ volatile("dmb" ::: "memory");
  g_up_mask_active = false;

  if (*pa != saved)
  {
    g_up_mask_restore_failures++;
    return 0;
  }
  return 1;
}

u32 hid_up_mask_stats()
{
  return (g_up_mask_begin_failures & 0xffff) |
         ((g_up_mask_restore_failures & 0xffff) << 16);
}
'''
HIDC.write_text(hc)

HIDH = Path('3gx/includes/hid.h')
hh = HIDH.read_text()
hh += '''\nu32 hid_up_mask_capable();\nu32 hid_up_mask_begin();\nu32 hid_up_mask_restore();\nu32 hid_up_mask_stats();\n'''
HIDH.write_text(hh)

# The pause loop must restore a transient HID mask before it samples user keys.
C = Path('3gx/sources/main.c')
c = C.read_text()
c = rep(
    c,
    '''    while (is_paused && !isTopScreen)\n    {\n        scan_input();\n''',
    '''    while (is_paused && !isTopScreen)\n    {\n        hid_up_mask_restore();\n        scan_input();\n''',
    'pause restore before scan',
)
C.write_text(c)

# Rust FFI wrappers for the C HID mask helpers.
B = Path('reader_core/src/pnp/bindings.rs')
b = B.read_text()
b = rep(
    b,
    '    pub fn get_current_keys() -> u32;\n',
    '''    pub fn get_current_keys() -> u32;
    pub fn hid_up_mask_capable() -> u32;
    pub fn hid_up_mask_begin() -> u32;
    pub fn hid_up_mask_restore() -> u32;
    pub fn hid_up_mask_stats() -> u32;
''',
    'pnp HID externs',
)
# test stubs are needed by cargo tests/lint builds.
b = rep(
    b,
    '''    #[no_mangle]\n    pub extern "C" fn get_current_keys() -> u32 {\n        0\n    }\n''',
    '''    #[no_mangle]
    pub extern "C" fn get_current_keys() -> u32 {
        0
    }
    #[no_mangle]
    pub extern "C" fn hid_up_mask_capable() -> u32 {
        1
    }
    #[no_mangle]
    pub extern "C" fn hid_up_mask_begin() -> u32 {
        1
    }
    #[no_mangle]
    pub extern "C" fn hid_up_mask_restore() -> u32 {
        1
    }
    #[no_mangle]
    pub extern "C" fn hid_up_mask_stats() -> u32 {
        0
    }
''',
    'pnp HID test stubs',
)
B.write_text(b)

I = Path('reader_core/src/pnp/input.rs')
i = I.read_text()
i += r'''

/// True when the mapped HID key word has a valid physical alias.
pub fn hid_mask_capable() -> bool {
    unsafe { bindings::hid_up_mask_capable() != 0 }
}

/// Temporarily hide physical UP from the next consumer of the shared HID word.
pub fn hid_mask_up_begin() -> bool {
    unsafe { bindings::hid_up_mask_begin() != 0 }
}

/// Restore the exact key word saved by hid_mask_up_begin().
pub fn hid_mask_up_restore() -> bool {
    unsafe { bindings::hid_up_mask_restore() != 0 }
}

/// (begin_failures, restore_failures).
pub fn hid_mask_stats() -> (u16, u16) {
    let bits = unsafe { bindings::hid_up_mask_stats() };
    ((bits & 0xffff) as u16, (bits >> 16) as u16)
}
'''
I.write_text(i)

# -------------------------------------------------------------------------
# Crystal hook live-pass state machine.
# -------------------------------------------------------------------------
H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()
anchor = 'static mut ATICKS: u64 = 0;\nstatic mut STICKS: u64 = 0;\n'
insert = r'''static mut ATICKS: u64 = 0;
static mut STICKS: u64 = 0;

// ---- v7.6.7 continuous physical-UP HID mask probe -----------------------
// `armed_advance` is frozen at B-ARM. The first resumed UpdateJoypad happens
// after the VBlank rDIV pair increments RNG_ADVANCE to armed+1. Therefore a
// true 16-input-frame mask means pass starts at armed+17, not armed+16.
const LIVE_MASK_FRAMES: u32 = 16;
const LIVE_PASS_FRAMES: u32 = 2;
const LIVE_POST_FRAMES: u32 = 4;
const RJOYP_ADDR: u32 = 0xff00;

#[derive(Clone, Copy)]
pub struct LivePassTelemetry {
    pub armed_advance: u32,
    pub first_input_advance: u32,
    pub pass_start_advance: u32,
    pub pass_end_advance: u32,
    pub capable: u8,
    pub rjoy_reads: u32,
    pub masked_rjoy_reads: u32,
    pub passed_rjoy_reads: u32,
    pub masked_advances: u8,
    pub passed_advances: u8,
    pub last_mask_advance: u32,
    pub last_pass_advance: u32,
    pub begin_failures: u16,
    pub restore_failures: u16,
    pub first_mask_advance: u32,
    pub first_mask_tick: u64,
    pub first_mask_mcycle: u8,
    pub first_mask_pc: u16,
    pub first_pass_advance: u32,
    pub first_pass_tick: u64,
    pub first_pass_mcycle: u8,
    pub first_pass_pc: u16,
    pub first_pass_direct_div: u8,
    pub first_pass_phase4: u16,
    pub first_remask_advance: u32,
    pub first_remask_tick: u64,
    pub first_remask_mcycle: u8,
    pub first_remask_pc: u16,
}

impl LivePassTelemetry {
    const EMPTY: Self = Self {
        armed_advance: 0,
        first_input_advance: 0,
        pass_start_advance: 0,
        pass_end_advance: 0,
        capable: 0,
        rjoy_reads: 0,
        masked_rjoy_reads: 0,
        passed_rjoy_reads: 0,
        masked_advances: 0,
        passed_advances: 0,
        last_mask_advance: 0,
        last_pass_advance: 0,
        begin_failures: 0,
        restore_failures: 0,
        first_mask_advance: 0,
        first_mask_tick: 0,
        first_mask_mcycle: 0,
        first_mask_pc: 0,
        first_pass_advance: 0,
        first_pass_tick: 0,
        first_pass_mcycle: 0,
        first_pass_pc: 0,
        first_pass_direct_div: 0,
        first_pass_phase4: 0,
        first_remask_advance: 0,
        first_remask_tick: 0,
        first_remask_mcycle: 0,
        first_remask_pc: 0,
    };
}

static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;

pub fn arm_live_pass_probe() -> bool {
    // There must be no transient mask left from an earlier aborted trial.
    let restored = pnp::hid_mask_up_restore();
    let capable = restored && pnp::hid_mask_capable();
    let base = rng_advance();
    unsafe {
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
        out.begin_failures = bf;
        out.restore_failures = rf;
        out
    }
}

pub fn live_pass_should_finish() -> bool {
    unsafe {
        if !LIVE_PASS_ARMED {
            return false;
        }
        let finish = LIVE_PASS.pass_end_advance.wrapping_add(LIVE_POST_FRAMES);
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
                LIVE_PASS.first_pass_phase4 = (((div as u16) << 6) | mcycle as u16) & 0x3fff;
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
}
'''
if anchor not in h:
    raise SystemExit('v767 hook state anchor missing')
h = h.replace(anchor, insert, 1)

old = '''fn gb_read_mem(regs: &[u32], _stack_pointer: *mut u32) {\n    unsafe { ANY_HITS = ANY_HITS.wrapping_add(1) };\n\n    if regs[0] != 0xff04 {\n        return;\n    }\n'''
new = '''fn gb_read_mem(regs: &[u32], _stack_pointer: *mut u32) {\n    // Restore the exact HID word from the previous temporarily masked rJOYP\n    // read before handling this GB read. Then, if this read itself is rJOYP,\n    // optionally mask UP immediately before returning to the original reader.\n    live_pass_restore_previous_mask();\n    let requested = regs[0];\n    live_pass_filter_rjoy(requested);\n\n    unsafe { ANY_HITS = ANY_HITS.wrapping_add(1) };\n\n    if requested != 0xff04 {\n        return;\n    }\n'''
if old not in h:
    raise SystemExit('v767 gb_read_mem anchor missing')
h = h.replace(old, new, 1)
H.write_text(h)

# Re-export live-pass armer.
M = Path('reader_core/src/crystal/mod.rs')
m = M.read_text()
m = rep(m, 'pub use hook::init_crystal;', 'pub use hook::{arm_live_pass_probe, init_crystal};', 'crystal hook export')
M.write_text(m)

# C ABI: B-arm asks Rust to validate and arm the HID mask probe.
L = Path('reader_core/src/lib.rs')
l = L.read_text()
anchor = '''#[no_mangle]\npub extern "C" fn run_frame() {\n'''
insert = '''#[no_mangle]\npub extern "C" fn arm_suicune_live_pass() -> u32 {\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\n        return crystal::arm_live_pass_probe() as u32;\n    }\n    0\n}\n\n#[no_mangle]\npub extern "C" fn run_frame() {\n'''
if anchor not in l:
    raise SystemExit('v767 lib arm export anchor missing')
l = l.replace(anchor, insert, 1)
L.write_text(l)

P = Path('3gx/includes/pokereader.h')
p = P.read_text()
if 'u32 arm_suicune_live_pass();' not in p:
    p = p.replace('void arm_suicune_probe();', 'void arm_suicune_probe();\nu32 arm_suicune_live_pass();')
P.write_text(p)

# Current generated UI is v7.3.3 TwoStageArm: B-only ARM, then physical UP.
C = Path('3gx/sources/main.c')
c = C.read_text()
state_anchor = 'static bool suicune_wait_up_after_b = false;\n'
if state_anchor not in c:
    raise SystemExit('v767 TwoStage state anchor missing')
c = c.replace(state_anchor, state_anchor + 'static bool suicune_live_pass_ready = false;\n', 1)

marker = '        if ((held & KEY_B) && !(held & KEY_Y)'
a = c.find(marker)
if a < 0:
    raise SystemExit('v767 B-arm block missing')
beg = c.find('{', a)
depth = 0
end = -1
for k in range(beg, len(c)):
    if c[k] == '{': depth += 1
    elif c[k] == '}':
        depth -= 1
        if depth == 0:
            end = k + 1
            break
block = c[a:end]
needle = '            arm_suicune_probe();\n'
if needle not in block:
    raise SystemExit('v767 B-arm arm_suicune_probe missing')
block = block.replace(needle, needle + '            suicune_live_pass_ready = arm_suicune_live_pass() != 0;\n', 1)
c = c[:a] + block + c[end:]

stage2 = '''        // v7.6.7 stage 2: after B release, only physical UP may remain.\n        // If HID masking could not be armed, stay frozen (fail closed).\n        // Otherwise resume the VC continuously; rJOYP reads are masked in\n        // Rust for 16 input frames, passed for 2, then masked again.\n        if (suicune_wait_up_after_b)\n        {\n            const u32 stage2_block = KEY_A | KEY_B | KEY_X | KEY_Y |\n                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R |\n                KEY_START | KEY_SELECT;\n            if ((held & stage2_block) != 0)\n            {\n                svcSleepThread(1000000);\n                continue;\n            }\n            if (held & KEY_DUP)\n            {\n                if (!suicune_live_pass_ready)\n                {\n                    svcSleepThread(1000000);\n                    continue;\n                }\n                suicune_wait_up_after_b = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                fixed_armed = false;\n                suicune_auto_resume_pending = false;\n                suicune_phase_lock_active = false;\n                suicune_start_phase_lock_active = false;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }'''
c = replace_braced_block(c, '        if (suicune_wait_up_after_b)', stage2, 'UP stage2')
C.write_text(c)

# -------------------------------------------------------------------------
# Trace auto-stop and telemetry CSV.
# -------------------------------------------------------------------------
T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
use_anchor = 'use super::reader::Gen2Reader;\n'
if use_anchor not in t:
    raise SystemExit('v767 trace import anchor missing')
t = t.replace(use_anchor, 'use super::hook::{live_pass_should_finish, live_pass_telemetry};\n' + use_anchor, 1)

anchor = '        if self.probe_active && window[2] == SUICUNE_SPECIES {\n'
insert = '''        // v7.6.7 stops only after the 2F pass and four remasked frames.\n        // The live HID filter remains armed until the host freeze takes effect.\n        if self.probe_session && live_pass_should_finish() {\n            self.stop();\n            self.save();\n            pnp::request_pause();\n            return;\n        }\n\n'''
if t.count(anchor) != 1:
    raise SystemExit(f'v767 trace result anchor count {t.count(anchor)}')
t = t.replace(anchor, insert + anchor, 1)

old_close = '''        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();\n'''
pos = t.rfind(old_close)
if pos < 0:
    raise SystemExit('v767 CSV close anchor missing')
new_close = r'''        pnp::trace_file_write(line.as_bytes());

        let lp = live_pass_telemetry();
        line.clear();
        let _ = write!(
            line,
            "\nlive_pass,version,armed_advance,first_input_advance,pass_start_advance,pass_end_advance,capable,rjoy_reads,masked_rjoy_reads,passed_rjoy_reads,masked_advances,passed_advances,begin_failures,restore_failures,first_mask_advance,first_mask_tick,first_mask_mcycle,first_mask_pc,first_pass_advance,first_pass_tick,first_pass_mcycle,first_pass_pc,first_pass_direct_div,first_pass_phase4,first_remask_advance,first_remask_tick,first_remask_mcycle,first_remask_pc\nLIVEPASS,V767,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{:02X},{:04X},{},{},{:02X},{:04X},{:02X},{:04X},{},{},{:02X},{:04X}\n",
            lp.armed_advance,
            lp.first_input_advance,
            lp.pass_start_advance,
            lp.pass_end_advance,
            lp.capable,
            lp.rjoy_reads,
            lp.masked_rjoy_reads,
            lp.passed_rjoy_reads,
            lp.masked_advances,
            lp.passed_advances,
            lp.begin_failures,
            lp.restore_failures,
            lp.first_mask_advance,
            lp.first_mask_tick,
            lp.first_mask_mcycle,
            lp.first_mask_pc,
            lp.first_pass_advance,
            lp.first_pass_tick,
            lp.first_pass_mcycle,
            lp.first_pass_pc,
            lp.first_pass_direct_div,
            lp.first_pass_phase4,
            lp.first_remask_advance,
            lp.first_remask_tick,
            lp.first_remask_mcycle,
            lp.first_remask_pc
        );
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();
'''
t = t[:pos] + t[pos:].replace(old_close, new_close, 1)
T.write_text(t)

print('Applied v7.6.7 temporary-HID rJOYP mask -> physical UP 2F pass -> remask probe')
