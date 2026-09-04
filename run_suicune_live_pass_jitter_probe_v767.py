from pathlib import Path

# The generated v7.4.4 -> v7.6.6 main.c has small comment/whitespace drift
# between branch snapshots. Patch the v7.6.7 apply-script source in memory so
# the Y+X arming block is located semantically instead of by a brittle exact
# multiline string, then execute the normal apply script.

src_path = Path('apply_suicune_live_pass_jitter_probe_v767.py')
s = src_path.read_text()

a = s.index("old = '''            if (just_pressed & KEY_X)")
b = s.index("\nanchor = '''        if (fixed_run_pending)", a)

replacement = r'''import re
pat = re.compile(
    r'(?P<indent>[ \t]*)if \(just_pressed & KEY_X\)\s*\{\s*arm_suicune_probe\(\);\s*\}',
    re.MULTILINE,
)
m = pat.search(c)
if not m:
    raise SystemExit('v767 Y+X semantic anchor missing')
indent = m.group('indent')
body = (
    indent + 'if (just_pressed & KEY_X)\n'
    + indent + '{\n'
    + indent + '    arm_suicune_probe();\n'
    + indent + '    arm_suicune_live_pass();\n'
    + indent + '    live_pass_pending = true;\n'
    + indent + '    // v7.6.7 does not use the old paused Exact2F runner.\n'
    + indent + '    fixed_frames_remaining = 0;\n'
    + indent + '    fixed_run_pending = false;\n'
    + indent + '    fixed_armed = false;\n'
    + indent + '    continue;\n'
    + indent + '}'
)
c = c[:m.start()] + body + c[m.end():]
'''

patched = s[:a] + replacement + s[b:]
exec(compile(patched, str(src_path), 'exec'), {'__name__': '__main__'})
