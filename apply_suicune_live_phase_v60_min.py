#!/usr/bin/env python3
from pathlib import Path

p = Path('reader_core/src/crystal/trace.rs')
s = p.read_text()

def rep(old, new, label):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    s = s.replace(old, new, 1)

rep('    early_live_state: u16,\n', '', 'remove live state field')
rep('            early_live_state: 0,\n', '', 'remove live state init')
rep('        self.early_live_state = 0;\n', '', 'remove live state reset')
rep('                    self.early_live_state = reader.rng_state();\n', '', 'remove GB-state gate read')
rep(
    'live_phase,version,profile,slot,valid,live_div,live_sub,live_phase,live_state,live_tick,stale_ap4,stale_atick,stale_age_ticks,post1_ap4,live_to_post1',
    'live_phase,version,profile,slot,valid,live_div,live_sub,live_phase,live_tick,stale_ap4,stale_atick,stale_age_ticks,post1_ap4,live_to_post1',
    'trim LIVE header',
)
rep(
    '"LIVE,V60,{},{},{},{:02X},{:02X},{:04X},{:04X},{},{:04X},{},{},{:04X},{}\\n",\n            profile, em.used_slot, self.early_live_valid, self.early_live_div, self.early_live_sub,\n            self.early_live_phase, self.early_live_state, self.early_live_tick,',
    '"LIVE,V60,{},{},{},{:02X},{:02X},{:04X},{},{:04X},{},{},{:04X},{}\\n",\n            profile, em.used_slot, self.early_live_valid, self.early_live_div, self.early_live_sub,\n            self.early_live_phase, self.early_live_tick,',
    'trim LIVE row',
)

p.write_text(s)
print('Minimized v6.0 gate probe to live DIV/subtick/tick only')
