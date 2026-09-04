from pathlib import Path

p = Path('apply_suicune_omnibus_exactpass_v768.py')
s = p.read_text()
old = '''def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v768 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)
'''
new = '''def rep(src, old, new, label):
    # The legacy LIVEPASS row is deliberately left structurally unchanged.
    # v7.6.8 neutral/redirect fields are exported by OMNI,V768 instead.
    if label in ('livepass header extra', 'livepass format extra', 'livepass args extra'):
        return src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v768 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)
'''
if s.count(old) != 1:
    raise SystemExit('v768 wrapper: rep() definition mismatch')
s = s.replace(old, new, 1)

# Keep the omnibus summary at exactly 22 columns / 22 Rust arguments.
# This is patched at source level before executing the generator so rustc and
# the safety audit both see the same final format string.
bad_omni = 'OMNI,V768,{:04X},{:02X},{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{},{},{},{},{},{},{},{}'
good_omni = 'OMNI,V768,{:04X},{:02X},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{},{},{},{},{},{},{}'
if s.count(bad_omni) != 1:
    raise SystemExit(f'v768 wrapper: OMNI format mismatch ({s.count(bad_omni)})')
s = s.replace(bad_omni, good_omni, 1)

exec(compile(s, str(p), 'exec'), {'__name__': '__main__', '__file__': str(p)})

# Make the live UI lineage unambiguous.  Older diagnostic internals remain
# intentionally versioned in their CSV rows, but the operator-facing status
# must identify the actual 3GX that is running.
tp = Path('reader_core/src/crystal/trace.rs')
t = tp.read_text()
ui_replacements = {
    'pnp::println!("S766 PHASE PROBE SCAN");': 'pnp::println!("V768 OMNIBUS SCAN");',
    'pnp::println!("S766 REL40 CAPTURED");': 'pnp::println!("V768 REL40 CAPTURED");',
    'pnp::println!("S766 A/r10 B76 LOCK");': 'pnp::println!("V768 A/r10 B76 LOCK");',
    'pnp::println!("S766 RESET RECOMMENDED");': 'pnp::println!("V768 RESET RECOMMENDED");',
}
for old_ui, new_ui in ui_replacements.items():
    if t.count(old_ui) != 1:
        raise SystemExit(f'v768 wrapper: UI marker mismatch for {old_ui!r} ({t.count(old_ui)})')
    t = t.replace(old_ui, new_ui, 1)
tp.write_text(t)
