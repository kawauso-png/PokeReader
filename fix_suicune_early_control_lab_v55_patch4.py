#!/usr/bin/env python3
from pathlib import Path
import re

p = Path("apply_suicune_early_control_lab_v55.py")
s = p.read_text()

start = s.find("# Detect 13 copies of rel26.")
end = s.find("# Save one compact lab row", start)
if start < 0 or end < 0:
    raise SystemExit("v5.5 detector script block not found")

block = r'''# Detect 13 copies of rel26. Insert immediately before the unique Suicune
# result check in Trace::record(). At that point self.len has already been
# incremented, so the just-sampled entry is entries[self.len - 1]. This avoids
# ambiguous self.len += 1 occurrences elsewhere (for example LineBuf::write_str).
t = rep(
    t,
    '''        if self.probe_active && window[2] == SUICUNE_SPECIES {''',
    '''        if self.probe_active && self.probe_session {
            let e = self.entries[self.len - 1];
            let rel = e.advance.wrapping_sub(self.start_advance);

            if !self.early_gate_seen && rel == 26 {
                self.early_rel26_count = self.early_rel26_count.saturating_add(1);
                if self.early_rel26_count == 13 {
                    self.early_gate_seen = true;
                    self.early_pre = early_point(e);
                    pnp::request_suicune_early_gate();
                }
            } else if self.early_gate_seen && self.early_post1.valid == 0
                && e.advance != self.early_pre.advance
            {
                self.early_post1 = early_point(e);
                self.early_j_a = phase_step_m(self.early_pre.ap4, self.early_post1.ap4) - 1172;
                self.early_j_s = phase_step_m(self.early_pre.sp4, self.early_post1.sp4) - 1172;
            } else if self.early_post1.valid != 0 && self.early_post2.valid == 0
                && e.advance != self.early_post1.advance
            {
                self.early_post2 = early_point(e);
                self.early_next_a = phase_step_m(self.early_post1.ap4, self.early_post2.ap4) - 1172;
                self.early_next_s = phase_step_m(self.early_post1.sp4, self.early_post2.sp4) - 1172;
            }
        }

        if self.probe_active && window[2] == SUICUNE_SPECIES {''',
    "detect rel26 gate and post transitions",
)

'''

s = s[:start] + block + s[end:]
p.write_text(s)
print("Anchored v5.5 Early detector at unique Suicune result check")
