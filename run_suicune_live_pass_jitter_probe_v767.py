from pathlib import Path

# v7.6.7 is maintained in the apply script. Keep the wrapper limited to
# generation-time hardening that depends on the exact generated v7.6.6 tree.

# hid.c needs the project declaration for svcConvertVAToPA used by common.h's
# physical-alias helper and by the v7.6.7 capability check.
hid_path = Path('3gx/sources/hid.c')
hid = hid_path.read_text()
if '#include "csvc.h"' not in hid:
    needle = '#include <3ds.h>\n'
    if hid.count(needle) != 1:
        raise SystemExit(f'wrapper: hid include anchor count {hid.count(needle)}')
    hid = hid.replace(needle, needle + '#include "csvc.h"\n', 1)
    hid_path.write_text(hid)

# Replace the brittle exact Suicune-result anchor used for trace auto-stop
# insertion with a semantic insertion after self.len += 1.
path = Path('apply_suicune_live_pass_jitter_probe_v767.py')
source = path.read_text()

start = source.find("anchor = '        if self.probe_active && window[2] == SUICUNE_SPECIES {\\n'")
if start < 0:
    raise SystemExit('wrapper: original trace auto-stop anchor block not found')
end = source.find("old_close = '''", start)
if end < 0:
    raise SystemExit('wrapper: CSV block boundary not found')

replacement = """record_start = t.find('    pub fn record(&mut self, reader: &Gen2Reader) {')
if record_start < 0:
    raise SystemExit('v767 trace record() not found')
len_pos = t.find('        self.len += 1;', record_start)
if len_pos < 0:
    raise SystemExit('v767 trace self.len increment not found')
line_end = t.find('\\n', len_pos)
if line_end < 0:
    raise SystemExit('v767 trace self.len line end not found')
line_end += 1
insert = (
    '        // v7.6.7 stops only after the 2F pass and four remasked frames.\\n'
    '        // The live HID filter remains armed until the host freeze takes effect.\\n'
    '        if self.probe_session && live_pass_should_finish() {\\n'
    '            self.stop();\\n'
    '            self.save();\\n'
    '            pnp::request_pause();\\n'
    '            return;\\n'
    '        }\\n\\n'
)
t = t[:line_end] + '\\n' + insert + t[line_end:]

"""
source = source[:start] + replacement + source[end:]
exec(compile(source, str(path), 'exec'), {'__name__': '__main__'})

# Fail-closed preflight: while the game is still paused and physical UP is
# already held, prove that the HID word can really be cleared and restored.
# This prevents the first live rJOYP read from being the first write test.
main_path = Path('3gx/sources/main.c')
c = main_path.read_text()
old = '''                if (!suicune_live_pass_ready)\n                {\n                    svcSleepThread(1000000);\n                    continue;\n                }\n                suicune_wait_up_after_b = false;\n'''
new = '''                if (!suicune_live_pass_ready)\n                {\n                    svcSleepThread(1000000);\n                    continue;\n                }\n                // v7.6.7 preflight occurs while still frozen. The game cannot\n                // observe this temporary clear; resume only after exact restore.\n                if (!hid_up_mask_begin())\n                {\n                    suicune_live_pass_ready = false;\n                    svcSleepThread(1000000);\n                    continue;\n                }\n                if (!hid_up_mask_restore())\n                {\n                    suicune_live_pass_ready = false;\n                    svcSleepThread(1000000);\n                    continue;\n                }\n                suicune_wait_up_after_b = false;\n'''
if c.count(old) != 1:
    raise SystemExit(f'wrapper: stage2 preflight anchor count {c.count(old)}')
c = c.replace(old, new, 1)
main_path.write_text(c)
