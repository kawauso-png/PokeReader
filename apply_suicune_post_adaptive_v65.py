#!/usr/bin/env python3
from pathlib import Path

trace_path = Path("reader_core/src/crystal/trace.rs")
text = trace_path.read_text()
lines = text.splitlines()

hits = [i for i, line in enumerate(lines) if "practical_checked40" in line]
if not hits:
    raise SystemExit("v6.5 debug: practical_checked40 not found")
for i in hits:
    lo = max(0, i - 12)
    hi = min(len(lines), i + 36)
    print(f"--- v6.5 rel40 context around line {i+1} ---")
    for j in range(lo, hi):
        print(f"{j+1}: {lines[j]}")

# Stop here deliberately. The next patch revision will replace the exact
# generated v6.4 behavior shown above rather than guessing its structure.
raise SystemExit("v6.5 debug rel40 context captured")
