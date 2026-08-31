#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.4: promote the two reproducible r00* bad rows seen on hardware into the
# special-20F transition model. Two independent live captures both showed:
#   d03 s12 g1 r00*
#   d04 s12 g0 r00*
# while all other readiness gates were locked (S4 D16, marker hits complete).
# Keep READY at 80/80; only add these exact observed transition classes.

if ! grep -q '(0x04, 0x12, 0)' "$ADPMOD"; then
    python3 - "$ADPMOD" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = '''        (0x02, 0x13, 1) |\n        (0x03, 0x12, 0) |\n        (0x03, 0x13, 0))'''
new = '''        (0x02, 0x13, 1) |\n        (0x03, 0x12, 0) |\n        (0x03, 0x12, 1) |\n        (0x03, 0x13, 0) |\n        (0x04, 0x12, 0))'''
if old not in s:
    raise SystemExit('allowed_special pattern not found')
p.write_text(s.replace(old, new, 1))
PY
fi

# Add regression assertions so later model edits cannot silently drop either
# hardware-observed special transition.
if ! grep -q 'hardware_special_rows_r00' "$ADPMOD"; then
    python3 - "$ADPMOD" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
needle = '''    #[test]\n    fn ready_threshold_requires_full_clean_window() {'''
insert = '''    #[test]\n    fn hardware_special_rows_r00_are_accepted() {\n        assert!(allowed_special(0x03, 0x12, 1));\n        assert!(allowed_special(0x04, 0x12, 0));\n    }\n\n'''
if needle not in s:
    raise SystemExit('test insertion point not found')
p.write_text(s.replace(needle, insert + needle, 1))
PY
fi

sed -i 's/BLUE LEGEND RNG v8.2.3 BADROW/BLUE LEGEND RNG v8.2.4 SPFIX/' "$RUST"
sed -i 's/ADAPT BADROW DIAG/ADAPT SPECIAL FIX/' "$RUST"
sed -i 's/"LEGEND,28,/"LEGEND,29,/' "$CTRACE"
