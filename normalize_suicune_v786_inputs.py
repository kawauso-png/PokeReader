#!/usr/bin/env python3
from pathlib import Path

p = Path('3gx/sources/main.c')
s = p.read_text()

# v7.8.5 generated comments use two spaces after sentence punctuation, while
# the v7.8.6 patch's semantic comparison text uses one. Normalize only these
# known comment phrases; executable code and string literals are untouched.
for old, new in (
    ('v7.8.5 SHINY PHASE PROBE.  The real-UP Exact2 mechanism is',
     'v7.8.5 SHINY PHASE PROBE. The real-UP Exact2 mechanism is'),
    ('// unchanged.  While still frozen, align the *release into* the',
     '// unchanged. While still frozen, align the *release into* the'),
    ('// display-cycle slot.  No RNG/DIV/GB input value is written.',
     '// display-cycle slot. No RNG/DIV/GB input value is written.'),
    ('// v7.8.5 start-slot selector.  Exact2 release/resume is deliberately',
     '// v7.8.5 start-slot selector. Exact2 release/resume is deliberately'),
    ('// transport-phase lever under test.',
     '// transport-phase lever under test.'),
):
    s = s.replace(old, new)

p.write_text(s)
print('Normalized v7.8.5 comment whitespace for v7.8.6 patch matching')
