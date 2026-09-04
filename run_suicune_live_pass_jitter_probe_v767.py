from pathlib import Path

# v7.6.7 is maintained in the apply script. This wrapper performs one narrow
# normalization only: replace the brittle exact Suicune-result anchor used for
# trace auto-stop insertion with a semantic insertion after self.len += 1.
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
