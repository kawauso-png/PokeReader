from pathlib import Path

# v7.6.7 is maintained in the apply script.  This wrapper only normalizes two
# deliberately brittle trace anchors before execution so generated v7.6.6
# whitespace/comment drift cannot prevent the diagnostic patch from applying.
path = Path('apply_suicune_live_pass_jitter_probe_v767.py')
source = path.read_text()

# 1) Auto-stop insertion: do not depend on the exact Suicune-result condition.
old = '''anchor = '        if self.probe_active && window[2] == SUICUNE_SPECIES {\\n'
insert = '''        // v7.6.7 stops only after the 2F pass and four remasked frames.\\n        // The live HID filter remains armed until the host freeze takes effect.\\n        if self.probe_session && live_pass_should_finish() {\\n            self.stop();\\n            self.save();\\n            pnp::request_pause();\\n            return;\\n        }\\n\\n'''
if t.count(anchor) != 1:
    raise SystemExit(f'v767 trace result anchor count {t.count(anchor)}')
t = t.replace(anchor, insert + anchor, 1)
'''
new = '''# Insert immediately after the frame has been committed and self.len advanced.
# This location is semantically stable across v7.6.x and is before any native
# Suicune-result auto-stop path.
record_start = t.find('    pub fn record(&mut self, reader: &Gen2Reader) {')
if record_start < 0:
    raise SystemExit('v767 trace record() not found')
len_pos = t.find('        self.len += 1;', record_start)
if len_pos < 0:
    raise SystemExit('v767 trace self.len increment not found')
line_end = t.find('\\n', len_pos)
if line_end < 0:
    raise SystemExit('v767 trace self.len line end not found')
line_end += 1
insert = '''        // v7.6.7 stops only after the 2F pass and four remasked frames.\\n        // The live HID filter remains armed until the host freeze takes effect.\\n        if self.probe_session && live_pass_should_finish() {\\n            self.stop();\\n            self.save();\\n            pnp::request_pause();\\n            return;\\n        }\\n\\n'''
t = t[:line_end] + '\\n' + insert + t[line_end:]
'''
if old not in source:
    raise SystemExit('wrapper: trace auto-stop source block not found')
source = source.replace(old, new, 1)

# 2) CSV append: insert telemetry immediately before the final close call,
# rather than matching the preceding write/blank-line formatting.
start = source.find("old_close = '''        pnp::trace_file_write(line.as_bytes());")
if start < 0:
    raise SystemExit('wrapper: CSV close source block start not found')
end_marker = "T.write_text(t)"
end = source.find(end_marker, start)
if end < 0:
    raise SystemExit('wrapper: CSV close source block end not found')
replacement = r'''close_anchor = '        pnp::trace_file_close();\n'
pos = t.rfind(close_anchor)
if pos < 0:
    raise SystemExit('v767 final trace_file_close not found')
telemetry = r'''        let lp = live_pass_telemetry();
        line.clear();
        let _ = write!(
            line,
            "\nlive_pass,version,armed_advance,first_input_advance,pass_start_advance,pass_end_advance,capable,rjoy_reads,masked_rjoy_reads,passed_rjoy_reads,masked_advances,passed_advances,begin_failures,restore_failures,first_mask_advance,first_mask_tick,first_mask_mcycle,first_mask_pc,first_pass_advance,first_pass_tick,first_pass_mcycle,first_pass_pc,first_pass_direct_div,first_pass_phase4,first_remask_advance,first_remask_tick,first_remask_mcycle,first_remask_pc\nLIVEPASS,V767,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{:02X},{:04X},{},{},{:02X},{:04X},{:02X},{:04X},{},{},{:02X},{:04X}\n",
            lp.armed_advance,
            lp.first_input_advance,
            lp.pass_start_advance,
            lp.pass_end_advance,
            lp.capable,
            lp.rjoy_reads,
            lp.masked_rjoy_reads,
            lp.passed_rjoy_reads,
            lp.masked_advances,
            lp.passed_advances,
            lp.begin_failures,
            lp.restore_failures,
            lp.first_mask_advance,
            lp.first_mask_tick,
            lp.first_mask_mcycle,
            lp.first_mask_pc,
            lp.first_pass_advance,
            lp.first_pass_tick,
            lp.first_pass_mcycle,
            lp.first_pass_pc,
            lp.first_pass_direct_div,
            lp.first_pass_phase4,
            lp.first_remask_advance,
            lp.first_remask_tick,
            lp.first_remask_mcycle,
            lp.first_remask_pc
        );
        pnp::trace_file_write(line.as_bytes());

'''
t = t[:pos] + telemetry + t[pos:]
T.write_text(t)

'''
source = source[:start] + replacement + source[end + len(end_marker):]

exec(compile(source, str(path), 'exec'), {'__name__': '__main__'})
