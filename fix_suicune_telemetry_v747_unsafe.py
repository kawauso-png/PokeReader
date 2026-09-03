#!/usr/bin/env python3
from pathlib import Path
P=Path('apply_suicune_telemetry_v747.py')
s=P.read_text()
old='''        RANDOM_PHASE_WORK_V747=RandomPhaseEntryV747{\n            index:unsafe{RANDOM_PHASE_COUNT_V747},'''
new='''        let work=RandomPhaseEntryV747{\n            index:unsafe{RANDOM_PHASE_COUNT_V747},'''
if old not in s: raise SystemExit('v747 unsafe work start anchor missing')
s=s.replace(old,new,1)
old='''            adiv_index:add_div_tracker().index().unwrap_or(0) as u16,\n            sdiv_index:sub_div_tracker().index().unwrap_or(0) as u16,\n        };\n        unsafe{RANDOM_PHASE_PENDING_V747=true;}'''
new='''            adiv_index:add_div_tracker().index().unwrap_or(0) as u16,\n            sdiv_index:sub_div_tracker().index().unwrap_or(0) as u16,\n        };\n        unsafe{RANDOM_PHASE_WORK_V747=work;RANDOM_PHASE_PENDING_V747=true;}'''
if old not in s: raise SystemExit('v747 unsafe work finish anchor missing')
s=s.replace(old,new,1)
P.write_text(s)
print('Fixed v7.4.7 RandomPhase static mut assignment boundary')
