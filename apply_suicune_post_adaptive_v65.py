#!/usr/bin/env python3
from pathlib import Path

trace_path = Path("reader_core/src/crystal/trace.rs")
text = trace_path.read_text()

old = '''        if self.practical_active && !self.practical_checked40 && rel >= 40 {
            self.practical_checked40 = true;
            if current.state != self.practical_expected40_state
                || current.div != self.practical_expected40_div
            {
                self.practical_fail(1);
                return;
            }
        }
'''
new = '''        if self.practical_active && !self.practical_checked40 && rel >= 40 {
            self.practical_checked40 = true;
            if current.state != self.practical_expected40_state
                || current.div != self.practical_expected40_div
            {
                // v6.5: PRE->POST is not one-to-one.  A valid practical
                // candidate may enter a different stop1 POST cell even when
                // the exact frozen Target/PRE root was correct.  Do not abort
                // the encounter here: mark it as a learning fallback and let
                // the normal probe run all the way through PURETAIL/DV so the
                // new POST cell becomes a complete donor trace.
                self.practical_miss = 1;
                self.practical_active = false;
                self.practical_candidate_valid = false;
            }
        }
'''
if old not in text:
    raise SystemExit("v6.5 rel40 practical_fail anchor not found")
text = text.replace(old, new, 1)

# Make the status explicit: MISS during a live probe is a learning fallback,
# not a paused/failed trial.
old2 = '''        } else if self.practical_miss != 0 {
            pnp::println!("S64 MISS {}", self.practical_miss);
        } else if self.practical_active {
'''
new2 = '''        } else if self.practical_miss != 0 && self.probe_session {
            pnp::println!("S65 LEARN {}", self.practical_miss);
        } else if self.practical_miss != 0 {
            pnp::println!("S65 MISS {}", self.practical_miss);
        } else if self.practical_active {
'''
if old2 not in text:
    raise SystemExit("v6.5 status anchor not found")
text = text.replace(old2, new2, 1)

# Persist a v6.5 marker in CSV output so a learning fallback is unmistakable.
anchor = '        line.push_str("PRACTICAL,V64,");\n'
if anchor not in text:
    raise SystemExit("v6.5 PRACTICAL CSV anchor not found")
text = text.replace(anchor, '        line.push_str("POSTADAPT,V65,");\n        push_u32(&mut line, self.practical_miss as u32);\n        line.push(\',\');\n        push_u32(&mut line, self.practical_active as u32);\n        line.push(\'\\n\');\n        line.push_str("PRACTICAL,V64,");\n', 1)

trace_path.write_text(text)
print("Applied Suicune Post-Adaptive v6.5 learning fallback")
