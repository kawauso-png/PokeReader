from pathlib import Path

c = Path('3gx/sources/main.c').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()
h = Path('reader_core/src/crystal/hook.rs').read_text()

checks = {
    'k lineage': 'HOOKLOCK,V767K' in c and t.count('V767K') >= 5,
    'ffa4 exact2 authority survives': 'JOY_HJOYPAD_DOWN' in h and 'FFA4 poll authority' in h,
    'hook train captured': 'suicune_hooklock_last_top_tick = top_tick;' in c,
    'relative anchor': 'u64 anchor = suicune_hooklock_last_top_tick;' in c,
    'relative slot offset': 'const u64 offset = (period * (u64)wanted) / 16ULL;' in c,
    'predicted hook': 'predicted_hook = target + (period - offset);' in c,
    'physical release required': 'if ((held & KEY_DUP) == 0)' in c[c.index('// v7.6.7k:'):c.index('if (suicune_release_resume_pending)')],
    'resume telemetry armed': 'suicune_obs_wait_resume_hook = true;' in c[c.index('// v7.6.7k:'):c.index('if (suicune_release_resume_pending)')],
}
block = c[c.index('// v7.6.7k:'):c.index('if (suicune_release_resume_pending)')]
checks['no tick-zero cycle lock in exact2 block'] = 'u64 cycle = now / SUICUNE_PHASE_PERIOD_TICKS' not in block
checks['no synthetic UP'] = '| KEY_DUP' not in block
checks['no ff00 return replacement'] = '0xff00' not in block.lower()

for name, ok in checks.items():
    if not ok:
        raise SystemExit(f'AUDIT K FAIL: {name}')

for forbidden in ['RNG_ADVANCE =', 'Gen2Reader', 'gb_mem::write', 'div() =', 'raw_dv =']:
    if forbidden in block:
        raise SystemExit(f'AUDIT K FAIL: forbidden control mutation token {forbidden}')

print('AUDIT K PASS: FFA4 Exact2 retained; Resume anchored to live top-hook train')
print('AUDIT K PASS: HOOKLOCK predicted-vs-actual next-hook telemetry present')
print('AUDIT K PASS: no input/RNG/DIV/GB-RAM/save mutation in k control path')