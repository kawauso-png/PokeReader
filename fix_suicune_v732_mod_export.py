#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/mod.rs')
s=p.read_text()
old='pub use frame::{arm_suicune_probe, run_frame};'
new='pub use frame::{arm_suicune_probe, run_frame, suicune_control_pause_cell};'
if s.count(old)!=1:
    raise SystemExit(f'v732 mod export expected 1 match, got {s.count(old)}')
s=s.replace(old,new,1)
p.write_text(s)
print('v7.3.2 crystal module export fixed after full patch chain')
