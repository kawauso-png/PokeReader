#!/usr/bin/env python3
from pathlib import Path

P=Path('apply_suicune_telemetry_v747.py')
s=P.read_text()
old="""# import hook helpers\nif 'random_phase_count_v747' not in t.split('};',1)[0]:\n    old='    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, measured_div, rng_advance,'\n    new='    deep_log_count, deep_log_entry, deep_log_start, deep_log_stop, host_frame_metrics_v747, measured_div, random_phase_count_v747, random_phase_entry_v747, rng_advance,'\n    t=rep(t,old,new,'trace hook imports')\n"""
new="""# import hook helpers. Later phase patches expand/reflow this use block, so\n# insert the v747 names semantically before its closing brace instead of\n# depending on one historical line layout.\nif 'random_phase_count_v747' not in t.split('};',1)[0]:\n    a=t.find('use super::hook::{')\n    z=t.find('};',a)\n    need(a>=0 and z>a,'trace hook use block missing')\n    ins='    host_frame_metrics_v747, random_phase_count_v747, random_phase_entry_v747,\\n'\n    t=t[:z]+ins+t[z:]\n"""
if old not in s:
    raise SystemExit('v747 import adapter source anchor missing')
s=s.replace(old,new,1)
P.write_text(s)
print('Fixed v7.4.7 telemetry trace import adapter for expanded v738 use block')
