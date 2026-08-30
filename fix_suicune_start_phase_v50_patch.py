#!/usr/bin/env python3
from pathlib import Path
p = Path('apply_suicune_start_phase_lock_v50.py')
s = p.read_text()
old_a = "'''                suicune_obs_fixed_release_tick = svcGetSystemTick();\\n                suicune_obs_fixed_start_tick = svcGetSystemTick();\\n                suicune_obs_wait_fixed_hook = true;'''"
new_a = "'''                suicune_obs_fixed_release_tick = svcGetSystemTick();\\n                fixed_run_pending = false;\\n                suicune_obs_fixed_start_tick = svcGetSystemTick();\\n                suicune_obs_wait_fixed_hook = true;'''"
old_b = "'''                suicune_obs_fixed_release_tick = svcGetSystemTick();\\n                if (suicune_auto_resume_pending && suicune_start_phase_lock_active && suicune_start_phase_anchor_tick != 0)"
new_b = "'''                suicune_obs_fixed_release_tick = svcGetSystemTick();\\n                fixed_run_pending = false;\\n                if (suicune_auto_resume_pending && suicune_start_phase_lock_active && suicune_start_phase_anchor_tick != 0)"
if s.count(old_a) != 1 or s.count(old_b) != 1:
    raise SystemExit(f'v50 meta-fix mismatch old={s.count(old_a)} new={s.count(old_b)}')
s = s.replace(old_a, new_a, 1).replace(old_b, new_b, 1)
p.write_text(s)
print('Fixed v5.0 start-phase generated-main match')
