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
forbid(hidc, '| KEY_DUP', 'synthetic/injected UP')
forbid(hidc, 'g_up_mask_saved |', 'modified restore word')
need(hidh, 'u32 hid_up_mask_begin();', 'HID header begin')
need(hidh, 'u32 hid_up_mask_restore();', 'HID header restore')
need(c, 'hid_up_mask_restore();\n        scan_input();', 'restore before paused HID scan')

# 2) Rust bridge must expose only mask/restore status, not game-memory writes.
need(bind, 'pub fn hid_up_mask_begin() -> u32;', 'Rust HID begin binding')
need(bind, 'pub fn hid_up_mask_restore() -> u32;', 'Rust HID restore binding')
need(pin, 'pub fn hid_mask_up_begin() -> bool', 'safe HID begin wrapper')
need(pin, 'pub fn hid_mask_up_restore() -> bool', 'safe HID restore wrapper')

# 3) Live pass acts only on hardware rJOYP (FF00), never hJoy* HRAM.
need(h, 'const RJOYP_ADDR: u32 = 0xff00;', 'rJOYP-only target')
forbid(h, 'JOY_HRAM_FIRST', 'hJoy range masking')
forbid(h, 'ZERO_SHADOW_GB', 'GB shadow byte')
forbid(h, 'regs[0] =', 'GB address redirect')
need(h, 'live_pass_restore_previous_mask();', 'restore at every GB read hook')
need(h, 'live_pass_filter_rjoy(requested);', 'rJOYP filter')
need(h, 'if requested != RJOYP_ADDR', 'rJOYP-only guard')
need(h, 'pnp::hid_mask_up_begin()', 'temporary HID clear')
need(h, 'pnp::hid_mask_up_restore()', 'temporary HID restore')
need(h, 'base.wrapping_add(1 + LIVE_MASK_FRAMES)', '16 full masked input frames before pass')
need(h, 'const LIVE_PASS_FRAMES: u32 = 2;', '2F pass width')
need(h, 'pub passed_advances: u8,', 'distinct pass advance counter')
need(h, 'LIVE_PASS.last_pass_advance != now', 'distinct pass advance accounting')
need(h, 'Gen2Reader::crystal().div();', 'direct pass-time rDIV')
need(h, 'first_pass_phase4', 'direct pass-time phase4')

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

# 5) Trace stops after the remasked post-window and LIVEPASS CSV is consistent.
need(t, 'use super::hook::{live_pass_should_finish, live_pass_telemetry};', 'trace live-pass import')
need(t, 'if self.probe_session && live_pass_should_finish()', 'auto-stop condition')
need(t, 'self.stop();\n            self.save();\n            pnp::request_pause();', 'stop-save-pause order')
need(t, 'first_pass_direct_div,first_pass_phase4', 'direct landing fields in CSV')
need(t, 'masked_advances,passed_advances', 'mask/pass advance fields in CSV')

csv_start = t.index('let lp = live_pass_telemetry();')
csv_end = t.index('pnp::trace_file_write(line.as_bytes());', csv_start)
csv = t[csv_start:csv_end]
m = re.search(r'let _ = write!\(\s*line,\s*"([^"]*LIVEPASS,V767[^"]*)",(.*?)\n\s*\);', csv, re.S)
if not m:
    raise SystemExit('AUDIT FAIL: could not parse LIVEPASS write! block')
fmt, args = m.groups()
placeholders = len(re.findall(r'\{[^}]*\}', fmt))
arg_count = len(re.findall(r'\blp\.', args))
if placeholders != arg_count:
    raise SystemExit(f'AUDIT FAIL: LIVEPASS format mismatch: {placeholders} placeholders vs {arg_count} lp args')

print('AUDIT PASS: v7.6.7 uses reversible temporary HID masking at rJOYP only')
print('AUDIT PASS: paused clear/restore preflight is required before continuous resume')
print('AUDIT PASS: no synthetic UP, no hJoy/GB-RAM redirect, no RNG/DIV mutation')
print(f'AUDIT INFO: LIVEPASS values={placeholders}, stage2_len={len(stage)}, live_len={len(live)}')
