#!/usr/bin/env python3
from pathlib import Path

p = Path("apply_suicune_early_control_lab_v55.py")
s = p.read_text()

old = '''def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return src.replace(old, new, 1)
'''
new = '''def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    # Endpoint patches add a second self.len increment in generated trace.rs.
    # The ordinary record() increment is the first occurrence and is the exact
    # place where the just-sampled rel26 entry still sits at entries[self.len].
    if label == "detect rel26 gate and post transitions":
        if n < 1:
            raise SystemExit(f"{label}: expected >=1 match, got {n}")
        return src.replace(old, new, 1)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return src.replace(old, new, 1)
'''

n = s.count(old)
if n != 1:
    raise SystemExit(f"rep helper: expected 1 match, got {n}")
s = s.replace(old, new, 1)
p.write_text(s)
print("Configured v5.5 detector to use first record anchor")
