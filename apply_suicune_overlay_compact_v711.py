#!/usr/bin/env python3
from pathlib import Path
import re

T = Path('reader_core/src/crystal/trace.rs')
D = Path('reader_core/src/crystal/draw.rs')
F = Path('reader_core/src/crystal/frame.rs')

t = T.read_text()
d = D.read_text()
f = F.read_text()

# v7.1.1 is display-only. Keep v7.1 search/guard/telemetry logic unchanged.
if 'S710 SCAN A{} C{} P{} X{} I{} E{}' not in t:
    raise SystemExit('v711: v7.1 SCAN anchor missing')
if 'S710 READY UP+B' not in t:
    raise SystemExit('v711: v7.1 READY anchor missing')
if 'STAGE3,V710' not in t or 'BRANCH710,V710' not in t:
    raise SystemExit('v711: v7.1 telemetry anchors missing')

# UI epoch only. Telemetry remains V710 on purpose so existing parsers keep working.
t = t.replace('"S710 ', '"S711 ')

# Split the long SCAN row. Match formatting independently because v7.1 generator is compact.
scan_re = re.compile(
    r'pnp::println!\(\s*"S711 SCAN A\{\} C\{\} P\{\} X\{\} I\{\} E\{\}",\s*'
    r'rng_advance\(\)\.wrapping_sub\(self\.practical_live_start_advance\),\s*'
    r'self\.practical_live_checked,\s*self\.practical_live_lane_frames,\s*'
    r'self\.practical_empirical_eval,\s*self\.practical_live_index_wait,\s*'
    r'self\.practical_live_exact_eval\s*\);', re.S)
new_scan = '''pnp::println!("S711 SCAN");
                pnp::println!(
                    "A{} C{} P{}",
                    rng_advance().wrapping_sub(self.practical_live_start_advance),
                    self.practical_live_checked,
                    self.practical_live_lane_frames
                );
                pnp::println!(
                    "X{} I{} E{}",
                    self.practical_empirical_eval,
                    self.practical_live_index_wait,
                    self.practical_live_exact_eval
                );'''
t, nscan = scan_re.subn(new_scan, t, count=1)
if nscan != 1:
    raise SystemExit(f'v711: SCAN block count {nscan}')

# READY in v7.1 is intentionally emitted as a compact one-liner. Regex avoids whitespace sensitivity.
ready_re = re.compile(
    r'if\s+self\.practical_empirical\s*\{?\s*'
    r'pnp::println!\("S711 READY UP\+B E\{\} W\{\} \{:04X\}",\s*'
    r'self\.practical_source,\s*self\.practical_support,\s*self\.practical_raw\)\s*\}?\s*'
    r'else\s*\{?\s*'
    r'pnp::println!\("S711 READY UP\+B L\{\} W\{\} \{:04X\}",\s*'
    r'self\.practical_lane,\s*self\.practical_support,\s*self\.practical_raw\)\s*\}?', re.S)
new_ready = '''if self.practical_empirical {
                pnp::println!("S711 READY UP+B");
                pnp::println!("E{} W{} DV{:04X}", self.practical_source, self.practical_support, self.practical_raw);
            } else {
                pnp::println!("S711 READY UP+B");
                pnp::println!("L{} W{} DV{:04X}", self.practical_lane, self.practical_support, self.practical_raw);
            }'''
t, nready = ready_re.subn(new_ready, t, count=1)
if nready != 1:
    raise SystemExit(f'v711: READY block count {nready}')

# Remove legacy diagnostic println macros from the RNG overlay only. Their data collection,
# CSV output, probe logic and fields remain untouched.
def strip_print_macros(src: str, markers):
    out = []
    pos = 0
    removed = 0
    needle = 'pnp::println!('
    while True:
        i = src.find(needle, pos)
        if i < 0:
            out.append(src[pos:])
            break
        out.append(src[pos:i])
        op = src.find('(', i)
        j = op
        depth = 0
        in_str = False
        esc = False
        while j < len(src):
            c = src[j]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '(':
                    depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
            j += 1
        if depth != 0:
            raise SystemExit('v711: unterminated println macro')
        if j < len(src) and src[j] == ';':
            j += 1
        macro = src[i:j]
        if any(m in macro for m in markers):
            removed += 1
        else:
            out.append(macro)
        pos = j
    return ''.join(out), removed

# These are legacy rows visible in the user's screenshot. Stage3 S711 rows are not matched.
markers = [
    '"Fix ', '"Lab ', '"Probe ', '"LiveSub ', '"TSub ', '"P4 ',
    '"NO RESULT', '"DV {:04X} D{}'
]
t, removed = strip_print_macros(t, markers)
if removed < 4:
    raise SystemExit(f'v711: expected legacy overlay rows, removed only {removed}')

# Compact the always-visible RNG values. Keep values useful for debugging/index lock.
d = d.replace('pnp::println!("ADIV Index {}", index)', 'pnp::println!("AI {}", index)')
d = d.replace('pnp::println!("Finding ADIV Index...")', 'pnp::println!("AI WAIT")')
d = d.replace('pnp::println!("SDIV Index {}", index)', 'pnp::println!("SI {}", index)')
d = d.replace('pnp::println!("Finding SDIV Index...")', 'pnp::println!("SI WAIT")')
d = d.replace('pnp::println!("State {:04X}", reader.rng_state());', 'pnp::println!("ST {:04X}", reader.rng_state());')
d = d.replace('pnp::println!("Advances {}", rng_advance());', 'pnp::println!("ADV {}", rng_advance());')
d = re.sub(r'\s*pnp::println!\(""\);\s*pnp::println!\("TID \{\}",\s*reader\.trainer_id\(\)\);', '', d, count=1)

# Trace/Save remain available in trace/CSV machinery; hide only RNG-page rows, format independently.
f = re.sub(
    r'(\s*state\.trace\.draw_rng_status\(\);)\s*'
    r'let \(status, start, len\) = state\.trace\.status_line\(\);\s*'
    r'pnp::println!\("Trace \{\} \{\} f\{\}", status, start, len\);\s*'
    r'let \(save, code\) = state\.trace\.save_status\(\);\s*'
    r'pnp::println!\("Save \{\} \{:08X\}", save, code\);',
    r'\1', f, count=1)

# Safety assertions: display patch only; Stage3 hard guards and telemetry stay intact.
for must in ['S711 SCAN', 'S711 READY UP+B', 'S711 LEARN D15', 'STAGE3,V710', 'BRANCH710,V710', 'S658 TEST']:
    if must not in t:
        raise SystemExit(f'v711: missing {must}')
if 'S710 SCAN' in t or 'S710 READY UP+B' in t:
    raise SystemExit('v711: stale S710 UI remains')
if 'Trace {} {} f{}' in f or 'Save {} {:08X}' in f:
    raise SystemExit('v711: RNG Trace/Save rows remain')
for must in ['"AI {}"', '"SI {}"', '"ST {:04X}"', '"ADV {}"']:
    if must not in d:
        raise SystemExit(f'v711: compact RNG field missing {must}')

T.write_text(t)
D.write_text(d)
F.write_text(f)
print(f'Applied Suicune v7.1.1 compact overlay; removed {removed} legacy println rows')
