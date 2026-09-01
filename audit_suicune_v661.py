#!/usr/bin/env python3
from pathlib import Path
import re

t = Path('reader_core/src/crystal/trace.rs').read_text()
checks = {
    'terminal field': 'practical_terminal_advance: u32' in t,
    'expiry 180': 'STATUS_CLEAR_AFTER_ADVANCES: u32 = 180' in t,
    'live clear call': 'self.clear_stale_practical_status();\n        self.practical_wait_monitor(reader);' in t,
    'fresh search reset': 'self.practical_terminal_advance = 0;\n        self.practical_candidate_valid = false;' in t,
    'branch fail stamp': 'self.practical_miss = code;\n        self.practical_terminal_advance = rng_advance();' in t,
    'result stamp': 'self.probe_result = Some(result);\n                self.probe_active = false;\n                self.practical_terminal_advance = rng_advance();' in t,
    'new idle': 'pnp::println!("S661 IDLE");' in t,
    'new wait': 'S661 WAIT' in t,
    'new ready': 'S661 READY UP+B' in t,
    'new retry': 'S661 RETRY B40 R>RESET' in t,
    'no old s660 UI': 'S660 ' not in t,
    'fast validate preserved': 'S658 TEST' in t,
    'lead preserved': 'MIN_SEARCH_LEAD' in t,
}
failed = [k for k, v in checks.items() if not v]
if failed:
    raise SystemExit('v6.6.1 audit failed: ' + ', '.join(failed))

errs = list(re.finditer(r'self\.practical_search_error = ([1-9][0-9]*);\n(\s*)self\.practical_terminal_advance = rng_advance\(\);', t))
all_nonzero = list(re.finditer(r'self\.practical_search_error = ([1-9][0-9]*);', t))
if len(errs) != len(all_nonzero):
    raise SystemExit(f'nonzero error stamp coverage mismatch: {len(errs)}/{len(all_nonzero)}')
if len(errs) < 8:
    raise SystemExit(f'too few terminal error stamps: {len(errs)}')

helper = t[t.index('fn clear_stale_practical_status'):t.index('fn practical_wait_monitor')]
if '|| self.practical_candidate_valid' in helper:
    raise SystemExit('stale helper incorrectly blocks successful-result cleanup')
if 'self.practical_candidate_valid = false;' not in helper:
    raise SystemExit('stale helper does not clear candidate flag')

print(f'Suicune v6.6.1 audit OK ({len(errs)} terminal error sites)')
