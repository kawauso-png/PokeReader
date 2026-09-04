from pathlib import Path
import re


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT FAIL: missing {label}: {needle!r}')


def forbid(text, needle, label):
    if needle in text:
        raise SystemExit(f'AUDIT FAIL: forbidden {label}: {needle!r}')


h = Path('reader_core/src/crystal/hook.rs').read_text()
c = Path('3gx/sources/main.c').read_text()
p = Path('3gx/includes/pokereader.h').read_text()
l = Path('reader_core/src/lib.rs').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()

# 1) GB-read filter and zero-shadow safety.
need(h, 'const JOY_HRAM_FIRST: u32 = 0xff98;', 'joy range start')
need(h, 'const JOY_HRAM_LAST: u32 = 0xff9f;', 'joy range end')
need(h, 'const ZERO_SHADOW_GB: u16 = 0xff97;', 'FF97-only shadow')
forbid(h, 'for gb in [0xff97u16, 0xff9cu16, 0xff98u16]', 'joy-byte shadow fallback')
need(h, 'pub fn arm_live_pass_probe() -> bool', 'fail-closed arm result')
need(h, 'LIVE_PASS_ARMED = ok;', 'arm only on valid shadow')
need(h, 'fn gb_read_mem(regs: &mut [u32]', 'mutable pre-dispatch regs')
need(h, 'let requested = regs[0];', 'preserved original GB address')
need(h, 'live_pass_filter_read(regs, requested);', 'joy filter invocation')
need(h, 'pub pass_advances: u8,', 'distinct passed-advance telemetry')
need(h, 'LIVE_PASS.last_pass_advance != now', 'distinct pass-advance accounting')

# The new live-pass block must observe/redirect only. No direct memory/RNG/DIV mutation.
block_a = h.index('// ---- v7.6.7 continuous physical-UP pass probe')
block_b = h.index('// Diagnostics for the legacy cycle hook', block_a)
live_block = h[block_a:block_b]
forbid(live_block, 'pnp::write(', 'memory write in live-pass block')
forbid(live_block, 'RNG_ADVANCE =', 'RNG advance mutation in live-pass block')
forbid(live_block, 'ADIV =', 'ADIV mutation in live-pass block')
forbid(live_block, 'SDIV =', 'SDIV mutation in live-pass block')
need(live_block, 'regs[0] = LIVE_PASS.zero_addr as u32;', 'read-address redirect')

# 2) C control must be B-arm -> UP-only continuous resume, fail closed.
need(p, 'u32 arm_suicune_live_pass();', 'C ABI readiness return')
need(l, 'pub extern "C" fn arm_suicune_live_pass() -> u32', 'Rust ABI readiness return')
need(c, 'static bool suicune_live_pass_ready = false;', 'persistent live-pass readiness')
need(c, 'suicune_live_pass_ready = arm_suicune_live_pass() != 0;', 'readiness capture on B arm')

stage_a = c.index('if (suicune_wait_up_after_b)')
stage_b = c.index('\n        }', stage_a) + len('\n        }')
stage = c[stage_a:stage_b]
need(stage, 'if (!suicune_live_pass_ready)', 'fail-closed UP stage')
need(stage, 'is_paused = false;', 'continuous resume')
forbid(stage, 'fixed_run_pending = true;', 'paused Exact2F scheduling')
forbid(stage, 'suicune_auto_resume_pending = true;', 'old auto-resume scheduling')

# 3) Trace must auto-stop/save after remask and include self-consistent LIVEPASS CSV.
need(t, 'use super::hook::{live_pass_should_finish, live_pass_telemetry};', 'trace live-pass import')
need(t, 'if self.probe_session && live_pass_should_finish()', 'live-pass auto-stop condition')
need(t, 'self.stop();\n            self.save();\n            pnp::request_pause();', 'stop-save-pause sequence')
need(t, 'pass_advances,last_pass_advance', 'LIVEPASS CSV pass columns')

stop_pos = t.index('if self.probe_session && live_pass_should_finish()')
result_pos = t.index('if self.probe_active && window[2] == SUICUNE_SPECIES', stop_pos)
if stop_pos >= result_pos:
    raise SystemExit('AUDIT FAIL: live-pass stop must precede normal Suicune result detector')

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
    raise SystemExit(f'AUDIT FAIL: LIVEPASS format args mismatch: {placeholders} placeholders vs {arg_count} lp args')

print('AUDIT PASS: v7.6.7 live-pass probe is fail-closed, read-only, continuous, and CSV-consistent')
print(f'AUDIT INFO: LIVEPASS fields={placeholders}, stage2_len={len(stage)}, live_block_len={len(live_block)}')
