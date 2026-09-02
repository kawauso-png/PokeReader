#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')

def need(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f'v717 missing {label}: {marker}')

t = T.read_text()
for marker, label in [
    ('S716 SCAN', 'v716 scan UI'),
    ('S716 READY UP+B', 'v716 ready UI'),
    ('S716 LEARN P', 'v716 LEARN UI'),
    ('reset_scan_epoch_v716', 'v716 epoch reset'),
    ('practical_miss', 'terminal miss state'),
    ('practical_search_error', 'terminal search error state'),
    ('fn practical_fail', 'branch fail handler'),
    ('FASTTAIL715,V715', 'v715 fingerprint telemetry'),
]:
    need(t, marker, label)

# Replace the old per-code RETRY/RESET wording with one automatic recommendation
# surface. LEARN stays higher priority and is intentionally excluded: a LEARN
# run should continue to DV capture rather than asking for a reset.
old_miss = '''        } else if self.practical_miss == 1 {
            pnp::println!("S716 RETRY B40 R>RESET");
        } else if self.practical_miss == 2 {
            pnp::println!("S716 RETRY B716 R>RESET");
        } else if self.practical_miss == 3 {
            pnp::println!("S716 RETRY B717 R>RESET");
        } else if self.practical_miss != 0 {
            pnp::println!("S716 RETRY M{} R>RESET", self.practical_miss);
'''
new_miss = '''        } else if self.practical_miss != 0 {
            pnp::println!("S717 RESET RECOMMENDED");
            if self.practical_miss == 1 {
                pnp::println!("WHY B40");
            } else if self.practical_miss == 2 {
                pnp::println!("WHY B716");
            } else if self.practical_miss == 3 {
                pnp::println!("WHY B717");
            } else {
                pnp::println!("WHY M{}", self.practical_miss);
            }
            pnp::println!("R > VC RESET");
'''
if old_miss not in t:
    raise SystemExit('v717 miss status block anchor missing')
t = t.replace(old_miss, new_miss, 1)

old_err = '''        } else if self.practical_search_error == 2 || self.practical_search_error == 3 {
            pnp::println!("S716 RESET VC E{}", self.practical_search_error);
        } else if self.practical_search_error != 0 {
            pnp::println!("S716 ERR {} K{}", self.practical_search_error, self.practical_search_skipped);
'''
new_err = '''        } else if self.practical_search_error != 0 {
            pnp::println!("S717 RESET RECOMMENDED");
            pnp::println!("WHY E{}", self.practical_search_error);
            pnp::println!("R > VC RESET");
'''
if old_err not in t:
    raise SystemExit('v717 search-error status block anchor missing')
t = t.replace(old_err, new_err, 1)

# UI epoch only. Current-root search, evaluator, CrossBranch, LearnAllPost,
# PureTailFingerprint and the v716 fresh-scan reset stay unchanged.
t = t.replace('"S716 ', '"S717 ')

# Guard against accidentally swallowing LEARN or changing the search model.
for marker in [
    'S717 SCAN',
    'S717 READY UP+B',
    'S717 LEARN P',
    'S717 RESET RECOMMENDED',
    'WHY B40', 'WHY B716', 'WHY B717', 'WHY E{}',
    'R > VC RESET',
    'reset_scan_epoch_v716',
    'fn practical_wait_monitor',
    'fn rebind_known_post_v713',
    'fn enter_stage3_learn',
    'practical_expected716_state',
    'practical_expected717_state',
    'FASTTAIL715,V715',
]:
    need(t, marker, marker)
if 'S716 SCAN' in t:
    raise SystemExit('v717 stale S716 SCAN remains')
if 'S717 RETRY ' in t or 'S717 RESET VC E' in t:
    raise SystemExit('v717 old manual reset wording remains')

T.write_text(t)
print('Applied Suicune v7.1.7 AutoResetAdvice: terminal failures automatically show RESET RECOMMENDED; LEARN remains uninterrupted')
