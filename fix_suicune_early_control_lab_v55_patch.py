#!/usr/bin/env python3
from pathlib import Path

p = Path("apply_suicune_early_control_lab_v55.py")
s = p.read_text()

old1 = '''t = rep(\n    t,\n    \'\'\'    probe_result: Option<ProbeResult>,\\n    /// Row shown first in the on screen table.\'\'\',\n    \'\'\'    probe_result: Option<ProbeResult>,\\n    // v5.5 Early Control Lab. These are reset only when Y+X arms a fresh\\n    // Suicune probe; start() calls reset() again and must not erase them.\\n    early_rel26_count: u8,\\n    early_gate_seen: bool,\\n    early_pre: EarlyLabPoint,\\n    early_post1: EarlyLabPoint,\\n    early_post2: EarlyLabPoint,\\n    early_j_a: i32,\\n    early_j_s: i32,\\n    early_next_a: i32,\\n    early_next_s: i32,\\n    /// Row shown first in the on screen table.\'\'\',\n    "add early trace fields",\n)'''
new1 = '''t = rep(\n    t,\n    \'\'\'    /// Row shown first in the on screen table.\'\'\',\n    \'\'\'    // v5.5 Early Control Lab. These are reset only when Y+X arms a fresh\\n    // Suicune probe; start() calls reset() again and must not erase them.\\n    early_rel26_count: u8,\\n    early_gate_seen: bool,\\n    early_pre: EarlyLabPoint,\\n    early_post1: EarlyLabPoint,\\n    early_post2: EarlyLabPoint,\\n    early_j_a: i32,\\n    early_j_s: i32,\\n    early_next_a: i32,\\n    early_next_s: i32,\\n    /// Row shown first in the on screen table.\'\'\',\n    "add early trace fields",\n)'''

old2 = '''t = rep(\n    t,\n    \'\'\'            probe_result: None,\\n            cursor: 0,\'\'\',\n    \'\'\'            probe_result: None,\\n            early_rel26_count: 0,\\n            early_gate_seen: false,\\n            early_pre: EarlyLabPoint::default(),\\n            early_post1: EarlyLabPoint::default(),\\n            early_post2: EarlyLabPoint::default(),\\n            early_j_a: 0,\\n            early_j_s: 0,\\n            early_next_a: 0,\\n            early_next_s: 0,\\n            cursor: 0,\'\'\',\n    "init early trace fields",\n)'''
new2 = '''t = rep(\n    t,\n    \'\'\'            cursor: 0,\'\'\',\n    \'\'\'            early_rel26_count: 0,\\n            early_gate_seen: false,\\n            early_pre: EarlyLabPoint::default(),\\n            early_post1: EarlyLabPoint::default(),\\n            early_post2: EarlyLabPoint::default(),\\n            early_j_a: 0,\\n            early_j_s: 0,\\n            early_next_a: 0,\\n            early_next_s: 0,\\n            cursor: 0,\'\'\',\n    "init early trace fields",\n)'''

for label, old, new in [("struct", old1, new1), ("default", old2, new2)]:
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 script match, got {n}")
    s = s.replace(old, new, 1)

p.write_text(s)
print("Fixed v5.5 generated trace insertion matches")
