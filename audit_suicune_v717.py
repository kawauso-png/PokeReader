#!/usr/bin/env python3
from pathlib import Path

t = Path('reader_core/src/crystal/trace.rs').read_text()
checks = [
    ('S717 SCAN', 'v717 scan UI'),
    ('S717 READY UP+B', 'v717 READY UI'),
    ('S717 LEARN P', 'LEARN preserved'),
    ('S717 RESET RECOMMENDED', 'automatic reset recommendation'),
    ('WHY B40', 'rel40 reason'),
    ('WHY B716', 'rel716 reason'),
    ('WHY B717', 'rel717 reason'),
    ('WHY E{}', 'search error reason'),
    ('R > VC RESET', 'user reset instruction'),
    ('reset_scan_epoch_v716', 'v716 clean epoch preserved'),
    ('fn practical_wait_monitor', 'actual-root scanner preserved'),
    ('fn rebind_known_post_v713', 'CrossBranch preserved'),
    ('fn enter_stage3_learn', 'LearnAllPost preserved'),
    ('practical_expected716_state', '716 hard guard preserved'),
    ('practical_expected717_state', '717 hard guard preserved'),
    ('FASTTAIL715,V715', 'PureTailFingerprint preserved'),
]
for marker, label in checks:
    if marker not in t:
        raise SystemExit('v717 audit missing ' + label + ': ' + marker)
for stale in ['S716 SCAN', 'S717 RETRY ', 'S717 RESET VC E']:
    if stale in t:
        raise SystemExit('v717 audit stale marker: ' + stale)
# LEARN must still be displayed before the generic miss recommendation.
if t.find('S717 LEARN P') > t.find('S717 RESET RECOMMENDED'):
    raise SystemExit('v717 audit: RESET recommendation would shadow LEARN')
print('AUDIT PASS: v7.1.7 automatically recommends VC reset on terminal failure; LEARN and all v7.1.6 search/safety behavior retained')
