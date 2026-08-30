#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
s = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    s = s.replace(old, new, 1)


# v4.7: coarse interval probe.  Instead of pausing at stop2, pause once at
# Target+16 and let the user hold A all the way to Endpoint.  This tests almost
# the entire encounter in one run.  If it changes the stop2/Endpoint trajectory,
# later builds can binary-search the latest effective start point.

replace_once(
    """    input_stop2_resume_repeats: u32,
    /// Row shown first in the on screen table.""",
    """    input_stop2_resume_repeats: u32,
    coarse_pause_requested: bool,
    coarse_pause_len: usize,
    /// Row shown first in the on screen table.""",
    "add v4.7 fields",
)

replace_once(
    """            input_stop2_resume_repeats: 0,
            cursor: 0,""",
    """            input_stop2_resume_repeats: 0,
            coarse_pause_requested: false,
            coarse_pause_len: 0,
            cursor: 0,""",
    "init v4.7 fields",
)

replace_once(
    """        self.input_stop2_resume_repeats = 0;""",
    """        self.input_stop2_resume_repeats = 0;
        self.coarse_pause_requested = false;
        self.coarse_pause_len = 0;""",
    "reset v4.7 fields",
)

# The old v4.6 stop2 pause is disabled.  We still capture stop2 state/phase so
# the same normalized residual calculation remains available.
replace_once(
    """                if !self.input_stop2_pause_requested {
                    self.input_stop2_pause_requested = true;
                    pnp::request_pause();
                }""",
    """                // v4.7: do not pause here; the coarse A-hold interval
                // already started at Target+16.
                self.input_stop2_pause_requested = false;""",
    "disable stop2 pause",
)

# Start the perturbation before the known early branch around rel~29.
replace_once(
    """        self.len += 1;
""",
    """        self.len += 1;

        if self.probe_active && !self.coarse_pause_requested {
            let rel = self.entries[self.len - 1]
                .advance
                .wrapping_sub(self.probe_target.advance);
            if rel >= 16 {
                self.coarse_pause_requested = true;
                self.coarse_pause_len = self.len;
                pnp::request_pause();
            }
        }
""",
    "insert coarse pause",
)

# Record stimulus from the first row after the Target+16 pause through Endpoint.
replace_once(
    """        if self.input_stop2_pause_requested
            && self.input_stop2_pause_len != 0
            && self.len > self.input_stop2_pause_len
            && self.endpoint.capture_advance == 0
        {""",
    """        if self.coarse_pause_requested
            && self.coarse_pause_len != 0
            && self.len > self.coarse_pause_len
            && self.endpoint.capture_advance == 0
        {""",
    "collect coarse stimulus",
)

# Replace the old stop2 instruction with the one early coarse instruction.
replace_once(
    """        if self.input_stop2_pause_requested
            && self.endpoint.capture_advance == 0
            && self.endpoint.stop2_advance != 0
        {
            pnp::println!(
                \"S46 +{} S{:04X}\",
                self.endpoint.stop2_offset,
                self.input_stop2_state
            );
            pnp::println!(\"HOLD BASE/UP/A + R\");
        }
""",
    """        if self.coarse_pause_requested
            && self.endpoint.capture_advance == 0
            && self.endpoint.stop2_advance == 0
        {
            pnp::println!(\"W47 +16 WHOLE EVENT\");
            pnp::println!(\"HOLD A + R, KEEP A\");
        }
""",
    "show v4.7 instruction",
)

s = s.replace('"EP46 +{} S{:04X}"', '"EP47 +{} S{:04X}"')

path.write_text(s)
print("Applied Suicune Coarse Input Probe v4.7")
