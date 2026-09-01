#!/usr/bin/env python3
from pathlib import Path
import re

TRACE = Path('reader_core/src/crystal/trace.rs')

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)

t = TRACE.read_text()

# Add a timestamp for terminal/old practical status. We cannot directly observe
# the VC menu's software-reset command from Rust, so terminal status is held
# while paused, then expires only after the emulated game has actually resumed
# and the RNG advance counter has moved a safe amount.
t = replace_once(
    t,
    '    practical_search_skipped: u8,\n    practical_search_from: u32,\n',
    '    practical_search_skipped: u8,\n    practical_terminal_advance: u32,\n    practical_search_from: u32,\n',
    'terminal field',
)
t = replace_once(
    t,
    '            practical_search_skipped: 0,\n            practical_search_from: 0,\n',
    '            practical_search_skipped: 0,\n            practical_terminal_advance: 0,\n            practical_search_from: 0,\n',
    'terminal init',
)

# Fresh Y+DOWN always starts a new visual epoch immediately.
t = replace_once(
    t,
    '        self.practical_search_error = 0;\n        self.practical_search_skipped = 0;\n        self.practical_candidate_valid = false;\n',
    '        self.practical_search_error = 0;\n        self.practical_search_skipped = 0;\n        self.practical_terminal_advance = 0;\n        self.practical_candidate_valid = false;\n',
    'fresh search clears terminal epoch',
)

# Every non-zero search error becomes a terminal status with an age anchor.
# This includes E2/E3 and hard diagnostics; zeroing assignments are untouched.
t, n = re.subn(
    r'(self\.practical_search_error = (?:[1-9][0-9]*);\n)(\s*)(?!self\.practical_terminal_advance)',
    lambda m: m.group(1) + m.group(2) + 'self.practical_terminal_advance = rng_advance();\n' + m.group(2),
    t,
)
if n < 8:
    raise SystemExit(f'expected >=8 nonzero search-error assignments, patched {n}')

# Branch guard failures are also terminal statuses.
t = replace_once(
    t,
    '    fn practical_fail(&mut self, code: u8) {\n        self.practical_miss = code;\n',
    '    fn practical_fail(&mut self, code: u8) {\n        self.practical_miss = code;\n        self.practical_terminal_advance = rng_advance();\n',
    'branch fail terminal stamp',
)

# A completed probe/result is terminal too. This prevents an old PATH from
# surviving into the next VC boot after the auto-save pause is released.
t = replace_once(
    t,
    '            if let Some(result) = result {\n                self.probe_result = Some(result);\n                self.probe_active = false;\n',
    '            if let Some(result) = result {\n                self.probe_result = Some(result);\n                self.probe_active = false;\n                self.practical_terminal_advance = rng_advance();\n',
    'successful result terminal stamp',
)

# Expire old UI/runtime state only after live RNG movement. While PokeReader is
# paused the advance does not move, so RETRY/ERR remains readable indefinitely.
# After R + VC software reset, normal VBlank RNG traffic clears it automatically.
marker = '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader) {\n'
insert = '''    fn clear_stale_practical_status(&mut self) {\n        const STATUS_CLEAR_AFTER_ADVANCES: u32 = 180;\n        if self.practical_terminal_advance == 0 {\n            return;\n        }\n        let age = rng_advance().wrapping_sub(self.practical_terminal_advance);\n        if age < STATUS_CLEAR_AFTER_ADVANCES {\n            return;\n        }\n\n        // Never clear a newly active run. Terminal stamps are set only on\n        // error/fail/result, but keep this guard explicit for future patches.\n        if self.probe_active || self.practical_search_enabled {\n            return;\n        }\n\n        self.practical_search_error = 0;\n        self.practical_search_skipped = 0;\n        self.practical_search_count = 0;\n        self.practical_search_index = 0;\n        self.practical_miss = 0;\n        self.practical_active = false;\n        self.practical_candidate_valid = false;\n        self.practical_terminal_advance = 0;\n    }\n\n'''
t = replace_once(t, marker, insert + marker, 'stale status helper')

# Called on live frames before WAIT logic. It does nothing while paused because
# record() itself is not advancing the emulated title then.
t = replace_once(
    t,
    '        if self.state == TraceState::Armed {\n            self.start(reader);\n        }\n\n        self.practical_wait_monitor(reader);\n',
    '        if self.state == TraceState::Armed {\n            self.start(reader);\n        }\n\n        self.clear_stale_practical_status();\n        self.practical_wait_monitor(reader);\n',
    'record stale status call',
)

# Make the new build visually unmistakable. This also avoids confusing a stale
# v6.6.0 screen with the new plugin during device testing.
t = t.replace('S660 ', 'S661 ')
t = t.replace('pnp::println!("S660 OFF");', 'pnp::println!("S661 IDLE");')
# Previous replacement already turns S660 OFF into S661 OFF.
t = t.replace('pnp::println!("S661 OFF");', 'pnp::println!("S661 IDLE");')

TRACE.write_text(t)
print(f'Applied Suicune v6.6.1 status epoch reset patch ({n} terminal errors stamped)')
