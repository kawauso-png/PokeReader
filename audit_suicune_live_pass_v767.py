from pathlib import Path
import re


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT FAIL: missing {label}: {needle!r}')


def forbid(text, needle, label):
    if needle in text:
        raise SystemExit(f'AUDIT FAIL: forbidden {label}: {needle!r}')


def braced_block(text, marker):
    a = text.index(marker)
    b = text.index('{', a)
    depth = 0
    for i in range(b, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[a:i + 1]
    raise SystemExit(f'AUDIT FAIL: unclosed block for {marker}')


h = Path('reader_core/src/crystal/hook.rs').read_text()
c = Path('3gx/sources/main.c').read_text()
hidc = Path('3gx/sources/hid.c').read_text()
hidh = Path('3gx/includes/hid.h').read_text()
p = Path('3gx/includes/pokereader.h').read_text()
l = Path('reader_core/src/lib.rs').read_text()
bind = Path('reader_core/src/pnp/bindings.rs').read_text()
pin = Path('reader_core/src/pnp/input.rs').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()

# 1) HID mask must be reversible and must never synthesize UP.
need(hidc, '#include "csvc.h"', 'svcConvertVAToPA declaration include')
need(hidc, 'u32 hid_up_mask_begin()', 'HID mask begin')
need(hidc, 'u32 original = *g_key_addr;', 'save exact HID word')
need(hidc, '*pa = original & ~KEY_DUP;', 'clear only UP')
need(hidc, 'g_up_mask_saved = original;', 'remember exact HID word')
need(hidc, '*pa = saved;', 'restore exact HID word')
need(hidc, 'u32 hid_up_mask_restore()', 'HID restore')
need(hidc, 'u32 hid_up_mask_capable()', 'HID capability gate')
need(hidc, 'PA_FROM_VA_PTR(g_key_addr)', 'physical alias access')
need(hidc, '((*pa | *g_key_addr) & KEY_DUP)', 'dual-view mask verification')
need(hidc, '*pa != saved || *g_key_addr != saved', 'dual-view restore verification')
forbid(hidc, '| KEY_DUP', 'synthetic/injected UP')
forbid(hidc, 'g_up_mask_saved |', 'modified restore word')
forbid(hidc, '__asm__ volatile("dmb"', 'ARMv7-only dmb on ARMv6K build')
need(hidh, 'u32 hid_up_mask_begin();', 'HID header begin')
need(hidh, 'u32 hid_up_mask_restore();', 'HID header restore')
restore_scan = 'hid_up_mask_restore();\n        scan_input();'
if c.count(restore_scan) < 2:
    raise SystemExit(f'AUDIT FAIL: expected restore before both paused/top key scans, got {c.count(restore_scan)}')

# 2) Rust bridge exposes only reversible HID mask/restore status.
need(bind, 'pub fn hid_up_mask_begin() -> u32;', 'Rust HID begin binding')
need(bind, 'pub fn hid_up_mask_restore() -> u32;', 'Rust HID restore binding')
need(pin, 'pub fn hid_mask_up_begin() -> bool', 'safe HID begin wrapper')
need(pin, 'pub fn hid_mask_up_restore() -> bool', 'safe HID restore wrapper')
need(pin, 'pub fn hid_mask_stats() -> (u16, u16)', 'HID failure telemetry wrapper')

# 3) Live pass acts only on hardware rJOYP (FF00), never hJoy* HRAM writes.
need(h, 'const RJOYP_ADDR: u32 = 0xff00;', 'rJOYP-only target')
forbid(h, 'JOY_HRAM_FIRST', 'hJoy range masking')
forbid(h, 'ZERO_SHADOW_GB', 'GB shadow byte')
forbid(h, 'regs[0] =', 'GB address redirect')
need(h, 'live_pass_restore_previous_mask();', 'restore at every GB read hook')
need(h, 'live_pass_filter_rjoy(requested);', 'rJOYP filter')
need(h, 'if requested != RJOYP_ADDR', 'rJOYP-only guard')
need(h, 'pnp::hid_mask_up_begin()', 'temporary HID clear')
need(h, 'pnp::hid_mask_up_restore()', 'temporary HID restore')
need(h, 'base.wrapping_add(1 + LIVE_MASK_FRAMES)', 'full masked input window before pass')
need(h, 'const LIVE_PASS_FRAMES: u32 = 2;', '2F pass width')
need(h, 'pub passed_advances: u8,', 'distinct host pass advance counter')
need(h, 'LIVE_PASS.last_pass_advance != now', 'distinct host pass advance accounting')
need(h, 'Gen2Reader::crystal().div();', 'direct pass-time rDIV')
need(h, '((mcycle as u16) & 0x3f)', 'F604 low-six-bit phase packing')
need(h, 'first_pass_phase4', 'direct pass-time phase4')

# Exact intended window constants and stop boundary.
def const_u32(name):
    m = re.search(rf'const {name}: u32 = (\d+);', h)
    if not m:
        raise SystemExit(f'AUDIT FAIL: could not parse {name}')
    return int(m.group(1))

mask_frames = const_u32('LIVE_MASK_FRAMES')
pass_frames = const_u32('LIVE_PASS_FRAMES')
post_frames = const_u32('LIVE_POST_FRAMES')
if (mask_frames, pass_frames, post_frames) != (16, 2, 4):
    raise SystemExit(f'AUDIT FAIL: window constants are {(mask_frames, pass_frames, post_frames)}, expected (16,2,4)')
need(h, 'LIVE_PASS.pass_end_advance.wrapping_add(LIVE_POST_FRAMES - 1)', 'four-frame remask stop boundary')

# Per-trial failure deltas: old failures must not poison later trials.
need(h, 'LIVE_PASS_BEGIN_FAILURE_BASE', 'begin failure baseline')
need(h, 'LIVE_PASS_RESTORE_FAILURE_BASE', 'restore failure baseline')
need(h, 'let (begin_base, restore_base) = pnp::hid_mask_stats();', 'failure baseline capture')
need(h, 'bf.wrapping_sub(LIVE_PASS_BEGIN_FAILURE_BASE)', 'begin failure trial delta')
need(h, 'rf.wrapping_sub(LIVE_PASS_RESTORE_FAILURE_BASE)', 'restore failure trial delta')

live_a = h.index('// ---- v7.6.7 continuous physical-UP HID mask probe')
live_b = h.index('// Diagnostics for the legacy cycle hook', live_a)
live = h[live_a:live_b]
forbid(live, 'pnp::write(', 'game/host memory writer from Rust live block')
forbid(live, 'host_write_mem', 'game memory write from live block')
forbid(live, 'RNG_ADVANCE =', 'RNG mutation')
forbid(live, 'ADIV =', 'ADIV mutation')
forbid(live, 'SDIV =', 'SDIV mutation')
forbid(live, 'gb_mem::write', 'GB RAM write')

# 4) Current B-only ARM -> UP-only continuous run; no paused Exact2F handoff.
need(p, 'u32 arm_suicune_live_pass();', 'C ABI readiness')
need(l, 'pub extern "C" fn arm_suicune_live_pass() -> u32', 'Rust ABI readiness')
need(c, 'static bool suicune_live_pass_ready = false;', 'C readiness state')
need(c, 'suicune_live_pass_ready = arm_suicune_live_pass() != 0;', 'B-arm readiness capture')
stage = braced_block(c, 'if (suicune_wait_up_after_b)')
need(stage, 'if (!suicune_live_pass_ready)', 'fail-closed stage2')
need(stage, 'if (!hid_up_mask_begin())', 'paused HID clear preflight')
need(stage, 'if (!hid_up_mask_restore())', 'paused HID restore preflight')
need(stage, 'suicune_live_pass_ready = false;', 'preflight failure latch')
need(stage, 'is_paused = false;', 'continuous resume')
if stage.index('if (!hid_up_mask_restore())') > stage.index('is_paused = false;'):
    raise SystemExit('AUDIT FAIL: HID preflight restore must occur before resume')
forbid(stage, 'fixed_run_pending = true;', 'old paused Exact2F scheduler')
forbid(stage, 'suicune_auto_resume_pending = true;', 'old timed-resume scheduler')

# 5) v7.6.7c must prove what Crystal itself received through hJoypadDown FF9A.
need(h, 'pub fn live_pass_observe_hjoypad_down(hjoy: u8)', 'game-side observer')
need(h, 'const PAD_UP: u8 = 0x40;', 'Gen2 UP bit')
need(h, 'game_mask_observed_advances', 'masked observed-frame counter')
need(h, 'game_pass_observed_advances', 'pass observed-frame counter')
need(h, 'game_remask_observed_advances', 'remask observed-frame counter')
need(h, 'game_mask_up_advances', 'masked game-UP counter')
need(h, 'game_pass_up_advances', 'passed game-UP counter')
need(h, 'game_remask_up_advances', 'remasked game-UP counter')
need(t, 'live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));', 'FF9A observation')
forbid(t, 'write_u8(0xff9a', 'FF9A write')
forbid(t, 'write_u16(0xff9a', 'FF9A write16')

# Observer must run before finish check so the fourth remasked frame is counted.
obs_pos = t.index('live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));')
stop_pos = t.index('if self.probe_session && live_pass_should_finish()', obs_pos)
if obs_pos >= stop_pos:
    raise SystemExit('AUDIT FAIL: FF9A observer must precede live-pass finish check')

# 6) Trace CSV must contain enough information to enforce the mechanics gate.
need(t, 'self.stop();\n            self.save();\n            pnp::request_pause();', 'stop-save-pause order')
need(t, 'first_pass_direct_div,first_pass_phase4', 'direct landing fields in CSV')
need(t, 'masked_advances,passed_advances', 'host mask/pass advance fields in CSV')
need(t, 'game_observed_advances,game_mask_observed_advances,game_pass_observed_advances,game_remask_observed_advances', 'game observed-window CSV fields')
need(t, 'game_mask_up_advances,game_pass_up_advances,game_remask_up_advances', 'game UP-window CSV fields')
need(t, 'LIVEPASS,V767C', 'verification-layer version stamp')

csv_start = t.index('let lp = live_pass_telemetry();')
csv_end = t.index('pnp::trace_file_write(line.as_bytes());', csv_start)
csv = t[csv_start:csv_end]
m = re.search(r'let _ = write!\(\s*line,\s*"([^"]*LIVEPASS,V767C[^"]*)",(.*?)\n\s*\);', csv, re.S)
if not m:
    raise SystemExit('AUDIT FAIL: could not parse LIVEPASS V767C write! block')
fmt, args = m.groups()
placeholders = len(re.findall(r'\{[^}]*\}', fmt))
arg_count = len(re.findall(r'\blp\.', args))
if placeholders != arg_count:
    raise SystemExit(f'AUDIT FAIL: LIVEPASS format mismatch: {placeholders} placeholders vs {arg_count} lp args')
if placeholders != 36:
    raise SystemExit(f'AUDIT FAIL: expected 36 V767C values, got {placeholders}')

# Algebraic sanity check for the first resumed advance = base+1 convention.
first_input = 1
pass_start = first_input + mask_frames
pass_end = pass_start + pass_frames
finish = pass_end + post_frames - 1
if (pass_start, pass_end, finish) != (17, 19, 22):
    raise SystemExit(f'AUDIT FAIL: relative window endpoints {(pass_start, pass_end, finish)} != (17,19,22)')

print('AUDIT PASS: v7.6.7c reversible HID mask + paused preflight + dual-view verification')
print('AUDIT PASS: exact game-side windows are 16 masked / 2 passed / 4 remasked advances')
print('AUDIT PASS: per-trial HID failures; FF9A read-only; no synthetic UP/RNG/DIV/GB-RAM mutation')
print(f'AUDIT INFO: LIVEPASS V767C values={placeholders}, endpoints=+{pass_start}/+{pass_end}/+{finish}')
