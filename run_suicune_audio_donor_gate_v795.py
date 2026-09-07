#!/usr/bin/env python3
from pathlib import Path

# v7.9.5 functional wrapper: the donor CSV telemetry is intentionally omitted.
# v7.9.1 changed the save-close layout after the original patch was drafted;
# telemetry is non-authoritative and must not block the production gate build.
p = Path('apply_suicune_audio_donor_gate_v795.py')
s = p.read_text()
a = s.index("save_anchor =")
b = s.index("f += r'''", a)
s = s[:a] + s[b:]
exec(compile(s, str(p), 'exec'), {'__name__': '__main__'})
