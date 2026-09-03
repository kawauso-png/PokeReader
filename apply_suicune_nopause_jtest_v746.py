#!/usr/bin/env python3
from pathlib import Path
import re

T = Path('reader_core/src/crystal/trace.rs')
F = Path('reader_core/src/crystal/frame.rs')
M = Path('3gx/sources/main.c')

t = T.read_text()
f = F.read_text()
m = M.read_text()


def need(cond, msg):
    if not cond:
        raise SystemExit('v746 ' + msg)


def rep(src, old, new, msg):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v746 {msg}: expected 1 got {n}')
    return src.replace(old, new, 1)

# ---------------------------------------------------------------------------
# v7.4.6 NOPAUSE J-test
# Diagnostic-only build.
# - Never calls host pause from Rust: host_request_pause() is a no-op.
# - Y+DOWN practical/live-root scan wrapper is disabled.
# - No authoritative root lock is ever armed because lane253 is never created.
# - User free-runs and physically performs B -> release -> UP -> release.
# - First observed physical UP after a complete B release arms the ordinary
#   Suicune probe in-place and then the existing trace/result/CSV path runs.
# - No HID injection and no RNG/state/DIV/DV writes.
# ---------------------------------------------------------------------------

# Stable compile-time marker inside trace.rs.
if 'const NOPAUSE_JTEST_V746: bool = true;' not in t:
    anchor = 'const MAX_FRAMES: usize = 8192;'
    need(anchor in t, 'MAX_FRAMES anchor missing')
    t = t.replace(anchor, anchor + '\nconst NOPAUSE_JTEST_V746: bool = true;', 1)

# Trace fields. Keep outside hot TraceEntry and do not alter legacy CSV rows.
if 'nptest_stage: u8,' not in t:
    anchor = '    pub cursor: usize,\n'
    need(anchor in t, 'Trace cursor field anchor missing')
    extra = '''    /// v7.4.6 free-run NOPAUSE diagnostic state.\n    nptest_stage: u8,\n    nptest_last_keys: u32,\n    nptest_trigger_advance: u32,\n    nptest_trigger_state: u16,\n    nptest_trigger_div: u16,\n'''
    t = t.replace(anchor, extra + anchor, 1)

if 'nptest_stage: 0,' not in t:
    anchor = '            cursor: 0,\n'
    need(anchor in t, 'Trace default cursor anchor missing')
    extra = '''            nptest_stage: 0,\n            nptest_last_keys: 0,\n            nptest_trigger_advance: 0,\n            nptest_trigger_state: 0,\n            nptest_trigger_div: 0,\n'''
    t = t.replace(anchor, extra + anchor, 1)

# Free-run B -> release -> UP state machine. Numeric HID bits match libctru:
# B=0x02, UP=0x40. This runs once per top-screen frame before Trace::record().
if 'pub fn nopause_jtest_tick(&mut self, reader: &Gen2Reader)' not in t:
    anchor = '    pub fn status_line(&self) -> (&\'static str, u32, usize) {'
    need(anchor in t, 'status_line method anchor missing')
    method = r'''    pub fn nopause_jtest_tick(&mut self, reader: &Gen2Reader) {
        if !NOPAUSE_JTEST_V746 { return; }
        let keys = pnp::current_keys();

        // Once the existing detector has locked a result, expose DONE but keep
        // the title free-running. save() remains the authoritative CSV writer.
        if self.nptest_stage == 3 && self.probe_result.is_some() {
            self.nptest_stage = 4;
        }

        match self.nptest_stage {
            0 => {
                // Require B physically down first.
                if (keys & 0x02) != 0 {
                    self.nptest_stage = 1;
                }
            }
            1 => {
                // A complete B release is mandatory before UP can trigger.
                if (keys & 0x02) == 0 {
                    self.nptest_stage = 2;
                }
            }
            2 => {
                // Ignore simultaneous B+UP; only UP after B release is legal.
                if (keys & 0x02) == 0 && (keys & 0x40) != 0 {
                    self.nptest_trigger_advance = rng_advance();
                    self.nptest_trigger_state = reader.rng_state();
                    self.nptest_trigger_div = measured_div();
                    // Reuse the ordinary probe/trace machinery. Unlike the
                    // production path this is called during free-run and no
                    // fixed-frame scheduler or root lock is involved.
                    self.arm_suicune_probe(reader);
                    self.nptest_stage = 3;
                }
            }
            _ => {}
        }
        self.nptest_last_keys = keys;
    }

'''
    t = t.replace(anchor, method + anchor, 1)

# Diagnostic status takes precedence over production selector UI.
if 'NPJT V746' not in t:
    sig = '    pub fn draw_rng_status(&self) {'
    pos = t.find(sig)
    need(pos >= 0, 'draw_rng_status missing')
    brace = t.find('{', pos)
    need(brace >= 0, 'draw_rng_status brace missing')
    insert = r'''
        if NOPAUSE_JTEST_V746 {
            pnp::println!("NPJT V746 NOPAUSE");
            match self.nptest_stage {
                0 => pnp::println!("WAIT B"),
                1 => pnp::println!("RELEASE B"),
                2 => pnp::println!("PRESS UP"),
                3 => pnp::println!("TRACE RUNNING"),
                _ => pnp::println!("DONE CSV SAVED"),
            }
            pnp::println!("ADV {}", rng_advance());
            pnp::println!("NO PAUSE / NO LOCK");
            return;
        }
'''
    t = t[:brace+1] + insert + t[brace+1:]

# Append-only schema marker. Legacy sections/headers are untouched.
if 'NPJT,V746' not in t:
    close = '        pnp::trace_file_close();'
    need(t.count(close) == 1, f'trace_file_close count {t.count(close)}')
    section = r'''        line.clear();
        let _ = write!(line,
            "\nnpause_jtest,version,mode,trigger_advance,trigger_state,trigger_div,stage,request_pause,root_lock,live_scan\nNPJT,V746,FREE_RUN,{},{:04X},{:04X},{},0,0,0\n",
            self.nptest_trigger_advance,
            self.nptest_trigger_state,
            self.nptest_trigger_div,
            self.nptest_stage
        );
        pnp::trace_file_write(line.as_bytes());

'''
    t = t.replace(close, section + close, 1)

# frame.rs: tick the free-run state machine immediately before normal record.
old = '    state.trace.record(&reader);\n'
new = '    state.trace.nopause_jtest_tick(&reader);\n    state.trace.record(&reader);\n'
if 'state.trace.nopause_jtest_tick(&reader);' not in f:
    need(f.count(old) == 1, f'frame record anchor count {f.count(old)}')
    f = f.replace(old, new, 1)

# Disable practical/live-root search at the exported wrapper. We patch the
# whole wrapper semantically so later production method internals do not matter.
if '// v7.4.6 NOPAUSE: practical scan intentionally disabled.' not in f:
    sig = 'pub fn search_suicune_practical_targets() {'
    a = f.find(sig)
    need(a >= 0, 'search_suicune_practical_targets wrapper missing')
    b = f.find('{', a)
    depth = 0
    e = -1
    for i in range(b, len(f)):
        if f[i] == '{': depth += 1
        elif f[i] == '}':
            depth -= 1
            if depth == 0:
                e = i + 1
                break
    need(e > b, 'search wrapper closing brace missing')
    repl = '''pub fn search_suicune_practical_targets() {\n    // v7.4.6 NOPAUSE: practical scan intentionally disabled.\n}\n'''
    f = f[:a] + repl + f[e:]

# C host: every Rust request_pause becomes a hard no-op in this diagnostic
# build. Manual L+R host pause still exists, but the test procedure never uses
# it. This also makes accidental production pause requests harmless.
if 'v7.4.6 NOPAUSE diagnostic: Rust pause requests are intentionally ignored.' not in m:
    pat = re.compile(r'void\s+host_request_pause\s*\(\s*(?:void\s*)?\)\s*\{.*?\}', re.S)
    hits = list(pat.finditer(m))
    need(len(hits) == 1, f'host_request_pause semantic matches {len(hits)}')
    repl = '''void host_request_pause(void)\n{\n    // v7.4.6 NOPAUSE diagnostic: Rust pause requests are intentionally ignored.\n}\n'''
    h = hits[0]
    m = m[:h.start()] + repl + m[h.end():]

# Safety assertions: preserve the proven physical TwoStage code in the source,
# but this mode never enters it because there is no selector/root-lock pause.
for marker in [
    'suicune_wait_up_after_b',
    'arm_suicune_probe();',
    'deep_log_start',
    'POSTFP',
]:
    need(marker in (m + t), f'safety/telemetry marker missing: {marker}')

T.write_text(t)
F.write_text(f)
M.write_text(m)
print('Applied Suicune v7.4.6 NOPAUSE J-test: free-run B-release-UP trigger, no live scan/root lock/request_pause')
