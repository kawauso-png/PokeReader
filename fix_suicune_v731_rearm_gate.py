#!/usr/bin/env python3
from pathlib import Path
P=Path('reader_core/src/crystal/trace.rs')
s=P.read_text()

# Do not let title/load transitions repeatedly restart the same RESET WAIT.
old='            if has_session && !encounter_executing {\n'
new='            if !self.soft_reset_rearm_pending && has_session && !encounter_executing {\n'
if s.count(old)!=1: raise SystemExit(f'v731 pending-epoch anchor count {s.count(old)}')
s=s.replace(old,new,1)

# Freshness must not depend on a known PRE class. v7.3 GlobalBeam deliberately
# removed that coverage bottleneck; only prove the ring/indices are from this
# new boot and current enough for evaluation.
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
print('Fixed v7.3.1 rearm: extra boot gaps acknowledged without re-wipe; fresh ring + ready A/S trackers; no PRE coverage dependency')
