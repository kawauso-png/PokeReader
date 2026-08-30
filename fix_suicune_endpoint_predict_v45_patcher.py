#!/usr/bin/env python3
from pathlib import Path

p = Path("apply_suicune_endpoint_predict_v45.py")
s = p.read_text()
old = '''    count = s.count(old)\n    if count != 1:\n        raise SystemExit(f"{label}: expected exactly one match, got {count}")\n    s = s.replace(old, new, 1)\n'''
new = '''    count = s.count(old)\n    if label == "extend endpoint snapshot":\n        if count < 1:\n            raise SystemExit(f"{label}: expected at least one match, got {count}")\n        # ProbeTarget has the same trailing stick/keys fields earlier in the\n        # file. EndpointSnapshot is the later occurrence inserted by v4.1.\n        pos = s.rfind(old)\n        s = s[:pos] + new + s[pos + len(old):]\n        return\n    if count != 1:\n        raise SystemExit(f"{label}: expected exactly one match, got {count}")\n    s = s.replace(old, new, 1)\n'''
if old not in s:
    raise SystemExit("replace_once body not found")
p.write_text(s.replace(old, new, 1))
print("Fixed v4.5 patch targeting for EndpointSnapshot")
