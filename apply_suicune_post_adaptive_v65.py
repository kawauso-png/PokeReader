#!/usr/bin/env python3
from pathlib import Path

trace_path = Path("reader_core/src/crystal/trace.rs")
text = trace_path.read_text()

# v6.4 has exactly one rel40 fail code. Replace only the fail action rather
# than matching the surrounding generated block; this is intentionally robust
# to formatting changes in the v6.4 generator. The following `return` stays in
# place and merely ends update_suicune_endpoint for that one frame. The probe
# remains active and continues normally on subsequent frames.
needle = "self.practical_fail(1);"
if text.count(needle) != 1:
    raise SystemExit(f"v6.5 rel40 fail anchor count: {text.count(needle)}")
replacement = '''{
                    // v6.5: PRE->POST is not one-to-one.  A valid frozen
                    // Target/PRE root may enter a different stop1 POST cell.
                    // Convert this candidate into a learning run instead of
                    // aborting: keep the normal probe alive through
                    // stop2/PURETAIL/DV and autosave the complete donor.
                    self.practical_miss = 1;
                    self.practical_active = false;
                    self.practical_candidate_valid = false;
                }'''
text = text.replace(needle, replacement, 1)

# While the live probe continues, label rel40 divergence as LEARN. Genuine
# later v6.4 path failures (2/3) still use practical_fail and pause, so once
# probe_session is no longer live they remain visibly MISS.
old_status = '''        } else if self.practical_miss != 0 {
            pnp::println!("S64 MISS {}", self.practical_miss);
        } else if self.practical_active {
'''
new_status = '''        } else if self.practical_miss != 0 && self.probe_session {
            pnp::println!("S65 LEARN {}", self.practical_miss);
        } else if self.practical_miss != 0 {
            pnp::println!("S65 MISS {}", self.practical_miss);
        } else if self.practical_active {
'''
if text.count(old_status) != 1:
    raise SystemExit(f"v6.5 status anchor count: {text.count(old_status)}")
text = text.replace(old_status, new_status, 1)

# Add a compact v6.5 CSV marker ahead of the existing v6.4 practical record.
anchor = '        line.push_str("PRACTICAL,V64,");\n'
if text.count(anchor) != 1:
    raise SystemExit(f"v6.5 CSV anchor count: {text.count(anchor)}")
insert = '''        line.push_str("POSTADAPT,V65,");
        push_u32(&mut line, self.practical_miss as u32);
        line.push(',');
        push_u32(&mut line, self.practical_active as u32);
        line.push('\\n');
        line.push_str("PRACTICAL,V64,");
'''
text = text.replace(anchor, insert, 1)

trace_path.write_text(text)
print("Applied Suicune Post-Adaptive v6.5 learning fallback")
