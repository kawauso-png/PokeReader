from pathlib import Path

p = Path('reader_core/src/crystal/boottrace.rs')
s = p.read_text()

old = '''            if hram.valid != 0
                && (hram.joypad_pressed != 0
                    || hram.joypad_released != 0
                    || hram.joy_pressed != 0
                    || hram.joy_released != 0)
            {
                reasons |= EV_JOY_EDGE;
            }
'''
new = '''            if hram.valid != 0
                && self.prev_hram.valid != 0
                && (hram.joypad_pressed != 0
                    || hram.joypad_released != 0
                    || hram.joypad_down != self.prev_hram.joypad_down
                    || hram.joypad_sum != self.prev_hram.joypad_sum
                    || hram.joy_pressed != self.prev_hram.joy_pressed
                    || hram.joy_released != self.prev_hram.joy_released
                    || hram.joy_down != self.prev_hram.joy_down
                    || hram.joy_last != self.prev_hram.joy_last)
            {
                reasons |= EV_JOY_EDGE;
            }
'''
if old not in s:
    raise SystemExit('missing JOY event block')
s = s.replace(old, new)

if 'const MAX_EVENTS: usize = 192;' not in s:
    raise SystemExit('missing MAX_EVENTS marker')
s = s.replace('const MAX_EVENTS: usize = 192;', 'const MAX_EVENTS: usize = 256;')

if 'mode,BOOT_ONESHOT_TRACE_V31' not in s:
    raise SystemExit('missing V31 mode marker')
s = s.replace('mode,BOOT_ONESHOT_TRACE_V31', 'mode,BOOT_ONESHOT_TRACE_V32')

p.write_text(s)
print('patched Boot One-shot v3.2 event filtering')
