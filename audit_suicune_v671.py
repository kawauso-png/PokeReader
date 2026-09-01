#!/usr/bin/env python3
from pathlib import Path

t = Path('reader_core/src/crystal/trace.rs').read_text()
p = Path('reader_core/src/crystal/practical.rs').read_text()
m = Path('3gx/sources/main.c').read_text()

checks = []

def must(cond, label):
    if not cond:
        raise SystemExit(f'FAIL: {label}')
    checks.append(label)

must('pub const ROLL_REFRESH_INTERVAL: u32 = 256;' in p, '256-advance rolling refresh')
must('pub const ROLL_LOCK_LEAD: u32 = 384;' in p, '384-advance final lock')
must('pub fn normal_inc_full(index: u32) -> u8' in p, 'v670 full-index DIV transport preserved')
must('0x0008 | 0x0009 | 0x0562 | 0x0563 | 0x22b5 | 0x22b6' in p, 'measured exception sites preserved')
must('fn rolling_refresh_targets(&mut self, reader: &Gen2Reader) -> bool' in t, 'rolling actual-root helper present')
must('self.practical_roll_count = self.practical_roll_count.saturating_add(1);' in t, 'rolling refresh counter')
must('if self.practical_roll_next != 0 && current >= self.practical_roll_next' in t, 'proactive rolling refresh gate')
must(t.count('if self.rolling_refresh_targets(reader) {') >= 3, 're-root used proactively and on misses')
must('self.practical_roll_eval = self.practical_roll_eval.saturating_add(1);' in t, 'EVAL counter')
must('self.practical_roll_pre = self.practical_roll_pre.saturating_add(1);' in t, 'PRE counter')
must('"ROLL,V671,{},{},{},{},{}\\n"' in t, 'V671 rolling telemetry')
must('"S671 WAIT {}/{} +{} R{}"' in t, 'V671 WAIT reroot display')
must('S671 READY UP+B' in t, 'UP+B READY path preserved')
must('S671 RETRY B40' in t and 'S671 RETRY B716' in t and 'S671 RETRY B717' in t, 'strict branch guards preserved')
must('FastValidate: hold UP and tap B' in m, 'host UP+B execution preserved')
must('KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R' in m, 'exact-UP safety mask preserved')
must('lane_for_post' not in t and 'evaluate_post' not in t, 'unsafe POST rebind still absent')

s = t.index('    fn rolling_refresh_targets(&mut self, reader: &Gen2Reader) -> bool')
e = t.index('    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)', s)
helper = t[s:e]
must('request_pause' not in helper, 'rolling helper has no pause')
must('request_resume' not in helper, 'rolling helper has no resume')
must('request_release_resume' not in helper, 'rolling helper has no release-resume')
must('self.stop()' not in helper and 'self.reset()' not in helper, 'rolling helper does not reset trace runtime')
must('let mut targets = [0u32; practical::MAX_SEARCH_CANDIDATES];' in helper, 'refresh builds queue off to the side')
must('if found == 0 {' in helper, 'empty refresh rejected before commit')

print(f'PASS: {len(checks)} v6.7.1 rolling-reroot invariants')
for x in checks:
    print(' -', x)
