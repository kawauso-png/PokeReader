#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
s = path.read_text()

old = '''        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;
        self.startsig_pc = 0;
        self.startsig_cpu_ctx = [0; STARTSIG_CPU_CTX_LEN];
        self.startsig_vb_valid = 0;
        self.startsig_vb_advance = 0;
        self.startsig_vb_div = 0;
        self.startsig_vb_mcycle = 0;
        self.startsig_vb_tick = 0;
        self.startsig_vb_regs = [0; 15];
        self.startsig_vb_stack = [0; 8];'''
new = '''        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;
        // v5.4: Do NOT clear Start Signature here. arm_suicune_probe() calls
        // reset() before latching the Target snapshot, but start() calls reset()
        // again on the first resumed frame. Clearing these fields here erased
        // the valid Y+X snapshot before save (0044-0046 diagnostics).
        // The next Suicune arm overwrites every startsig field explicitly.'''

count = s.count(old)
if count != 1:
    raise SystemExit(f"preserve startsig reset block: expected 1 match, got {count}")
s = s.replace(old, new, 1)

# Build marker in the CSV status makes it unambiguous which preservation fix
# produced a trace; the column layout stays identical to v5.3.
s = s.replace('"STARTSIG,V53,', '"STARTSIG,V54,', 1)
if '"STARTSIG,V54,' not in s:
    raise SystemExit("V54 CSV marker replacement failed")

path.write_text(s)
print("Applied Suicune Start Signature preservation v5.4")
