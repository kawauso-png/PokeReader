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
exec(compile(s, str(p), 'exec'), {'__name__': '__main__', '__file__': str(p)})
