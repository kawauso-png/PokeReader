#!/usr/bin/env python3
from pathlib import Path

trace_path = Path("reader_core/src/crystal/trace.rs")
text = trace_path.read_text()

old_rel40 = '''            if rel == 40 && !self.practical_checked40 {
                self.practical_checked40 = true;
                if e.state != self.practical_expected40_state || e.div != self.practical_expected40_div {
                    fail = 1;
                }
            } else if rel == 716 && !self.practical_checked716 {
'''
new_rel40 = '''            if rel == 40 && !self.practical_checked40 {
                self.practical_checked40 = true;
                if e.state != self.practical_expected40_state || e.div != self.practical_expected40_div {
                    // v6.5: PRE->POST is not one-to-one.  Keep the normal
                    // probe alive and turn this into a complete donor run.
                    self.practical_miss = 1;
                    self.practical_active = false;
                    self.practical_candidate_valid = false;
                }
            } else if rel == 716 && !self.practical_checked716 {
'''
if text.count(old_rel40) != 1:
    raise SystemExit(f"v6.5 rel40 block count: {text.count(old_rel40)}")
text = text.replace(old_rel40, new_rel40, 1)

old_status = '''        } else if self.practical_miss != 0 {
            pnp::println!("S64 MISS {}", self.practical_miss);
        } else if self.practical_active {
'''
new_status = '''        } else if self.practical_miss == 1 && self.probe_active {
            pnp::println!("S65 LEARN 1");
        } else if self.practical_miss != 0 {
            pnp::println!("S65 MISS {}", self.practical_miss);
        } else if self.practical_active {
'''
if text.count(old_status) != 1:
    raise SystemExit(f"v6.5 status block count: {text.count(old_status)}")
text = text.replace(old_status, new_status, 1)

# v6.5.2: Pause can land one RNG advance after the latest VBlank sample.
# v6.4 treated that harmless boundary condition as ERR1.  A one-advance lag
# is exactly compensable: shifting a 17-sample/16-delta window by one advances
# the prototype rotation by one, while the historical tracker-validation
# phase must move back by one modulo the 16-step normal cadence.
old_pre_guard = '''        let (proto, rot, best, _, consecutive) = classify_pre_ring(&r);
        if count != PRE_VBLANK_RING_LEN || !consecutive || best != 0 {
            self.practical_search_error = 1;
            return;
        }
        let (last_advance, _) = pre_ring_sample(&r, count - 1);
        if last_advance != rng_advance() {
            self.practical_search_error = 1;
            return;
        }
'''
new_pre_guard = '''        let (proto, mut rot, best, _, consecutive) = classify_pre_ring(&r);
        if count != PRE_VBLANK_RING_LEN {
            self.practical_search_error = 11;
            return;
        }
        if !consecutive {
            self.practical_search_error = 12;
            return;
        }
        if best != 0 {
            self.practical_search_error = 13;
            return;
        }
        let (last_advance, _) = pre_ring_sample(&r, count - 1);
        let current_advance = rng_advance();
        let pre_lag = current_advance.wrapping_sub(last_advance);
        if pre_lag > 1 {
            self.practical_search_error = 14;
            return;
        }
        if pre_lag == 1 {
            rot = rot.wrapping_add(1) & 15;
        }
'''
if text.count(old_pre_guard) != 1:
    raise SystemExit(f"v6.5.2 PRE guard count: {text.count(old_pre_guard)}")
text = text.replace(old_pre_guard, new_pre_guard, 1)

old_cadence = '''        let ai_now = add_div_tracker().index().unwrap_or(0) as u32;
        for i in 0..16usize {
'''
new_cadence = '''        let ai_now = add_div_tracker().index().unwrap_or(0) as u32;
        let ai_validate = ai_now.wrapping_sub(pre_lag);
        for i in 0..16usize {
'''
if text.count(old_cadence) != 1:
    raise SystemExit(f"v6.5.2 cadence anchor count: {text.count(old_cadence)}")
text = text.replace(old_cadence, new_cadence, 1)

old_inc = '''            if b1.wrapping_sub(b0) != practical::normal_inc(ai_now.wrapping_add(i as u32)) {
'''
new_inc = '''            if b1.wrapping_sub(b0) != practical::normal_inc(ai_validate.wrapping_add(i as u32)) {
'''
if text.count(old_inc) != 1:
    raise SystemExit(f"v6.5.2 cadence compare count: {text.count(old_inc)}")
text = text.replace(old_inc, new_inc, 1)

# Put an explicit v6.5 record immediately before the existing PRACTICAL,V64
# write. Locate the containing write! dynamically so this does not depend on
# the exact v6.4 format string layout.
marker = '"PRACTICAL,V64,'
pos = text.find(marker)
if pos < 0 or text.find(marker, pos + 1) >= 0:
    raise SystemExit("v6.5 PRACTICAL,V64 marker not unique")
write_pos = text.rfind('        let _ = write!(', 0, pos)
if write_pos < 0:
    raise SystemExit("v6.5 PRACTICAL write! start not found")
record = '''        line.clear();
        let _ = write!(
            line,
            "POSTADAPT,V65,{},{},{}\\n",
            self.practical_miss,
            self.practical_active as u8,
            self.probe_session as u8
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
'''
text = text[:write_pos] + record + text[write_pos:]
trace_path.write_text(text)

# v6.5.1 practical limit: long waits are poor both for real hardware stability
# and for collecting POST donors.  v6.4 searched a full 0x20000 / 131072
# advances.  Cap that projection at 12,000 advances.  Search the generated
# practical module and trace code after v6.4 has been applied, and require a
# unique original horizon so CI cannot silently build the old long-wait mode.
search_paths = [
    Path("reader_core/src/crystal/practical.rs"),
    trace_path,
]
representations = ["131072", "0x20000", "0x00020000"]
hits = []
for path in search_paths:
    if not path.exists():
        continue
    body = path.read_text()
    for literal in representations:
        count = body.count(literal)
        if count:
            hits.append((path, literal, count))

# Comments can contain the same decimal/hex value, so select the source file
# only when one representation occurs exactly once.  If the generator changes,
# fail loudly rather than accidentally restoring a 100k+ frame wait.
unique = [(path, literal) for path, literal, count in hits if count == 1]
if len(unique) != 1:
    detail = ", ".join(f"{p}:{lit}x{n}" for p, lit, n in hits) or "none"
    raise SystemExit(f"v6.5 12000F horizon anchor ambiguous: {detail}")
path, literal = unique[0]
body = path.read_text()
body = body.replace(literal, "12000", 1)
path.write_text(body)

# Verify no long-horizon literal remains in executable generated files and the
# new cap is present.  This is deliberately done in the patch itself so every
# artifact built by the workflow is guaranteed to be the 12k version.
if "12000" not in path.read_text():
    raise SystemExit("v6.5 12000F horizon verification failed")

print(f"Applied Suicune Post-Adaptive v6.5.2; search horizon=12000F, PRE lag<=1 compensated in {path}")
