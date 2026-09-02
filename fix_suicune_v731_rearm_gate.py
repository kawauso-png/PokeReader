#!/usr/bin/env python3
from pathlib import Path
P=Path('reader_core/src/crystal/trace.rs')
s=P.read_text()
old='        let pre_fresh = self.live_pre_cell().is_some();\n'
new='''        // Freshness must NOT depend on matching a known PRE prototype. v7.3
        // GlobalBeam intentionally removed that coverage bottleneck. The ring
        // only proves these samples belong to the new VC boot; the two full
        // DIV trackers prove evaluator indices are ready.
        let rr = latest_pre_vblank_ring();
        let rn = (rr.count as usize).min(PRE_VBLANK_RING_LEN);
        let ring_current = if rn == PRE_VBLANK_RING_LEN {
            let (last_adv, _) = pre_ring_sample(&rr, rn - 1);
            rng_advance().wrapping_sub(last_adv) <= 1
        } else {
            false
        };
        let pre_fresh = ring_current
            && add_div_tracker().index().is_some()
            && sub_div_tracker().index().is_some();
'''
if s.count(old)!=1: raise SystemExit(f'v731 rearm-gate anchor count {s.count(old)}')
s=s.replace(old,new,1)
P.write_text(s)
print('Fixed v7.3.1 rearm gate: fresh ring + ready A/S trackers, independent of PRE class/coverage')
