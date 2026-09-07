#!/usr/bin/env python3
from pathlib import Path

P=Path('apply_suicune_audio_donor_gate_v795.py')
s=P.read_text()
old='''m=M.read_text()\nm=rep(m,"pub use frame::{arm_suicune_probe, run_frame};",\n      "pub use frame::{arm_suicune_probe, audio_donor_gate, run_frame};","mod export")\nM.write_text(m)'''
new='''m=M.read_text()\n# v7.3.2+ already rewrites the grouped frame export. Add one independent\n# re-export instead of depending on the exact generated brace list.\nif "pub use frame::audio_donor_gate;" not in m:\n    m += "\\npub use frame::audio_donor_gate;\\n"\nM.write_text(m)'''
if old not in s:
    raise SystemExit('v795 fix: target block not found')
P.write_text(s.replace(old,new,1))
print('Normalized v7.9.5 crystal/mod.rs export patch for generated Stage3 source')
