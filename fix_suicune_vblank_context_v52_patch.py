#!/usr/bin/env python3
from pathlib import Path
p = Path('apply_suicune_vblank_context_v52.py')
s = p.read_text()
old = '''t = rep(\n    t,\n    \'\'\'    sdiv_cycles, sdiv_subtick, sdiv_tick, sub_div_tracker,\\n};\'\'\',\n    \'\'\'    sdiv_cycles, sdiv_subtick, sdiv_tick, sub_div_tracker, latest_vblank_context,\\n};\'\'\',\n    "import latest vblank context",\n)'''
new = '''if "latest_vblank_context" not in t:\n    start = t.find("use super::hook::{")\n    if start < 0:\n        raise SystemExit("import latest vblank context: hook import block not found")\n    end = t.find("};", start)\n    if end < 0:\n        raise SystemExit("import latest vblank context: hook import end not found")\n    t = t[:end] + "    latest_vblank_context,\\n" + t[end:]'''
if old not in s:
    raise SystemExit('v5.2 fixer: expected import patch block not found')
p.write_text(s.replace(old, new, 1))
print('Fixed v5.2 generated trace import match')
