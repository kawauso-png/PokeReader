#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path('.')
TRACE = (ROOT / 'reader_core/src/crystal/trace.rs').read_text()
PRACTICAL = (ROOT / 'reader_core/src/crystal/practical.rs').read_text()
HOOK = (ROOT / 'reader_core/src/pnp/hook.rs').read_text()
BIND = (ROOT / 'reader_core/src/pnp/bindings.rs').read_text()
MAIN = (ROOT / '3gx/sources/main.c').read_text()


def need(cond, msg):
    if not cond:
        raise SystemExit('v6.6.0 audit failed: ' + msg)

need('pub const SEARCH_HORIZON: u32 = 12000;' in PRACTICAL, '12k horizon changed')
need('pub const MIN_SEARCH_LEAD: u32 = 180;' in PRACTICAL, 'release lead missing')
need('pub const MIN_SUPPORT_WEIGHT: u8 = 4;' in PRACTICAL, 'support threshold changed')
need('for step in 1..=practical::SEARCH_HORIZON' in TRACE, 'projection must simulate every step')
need('if step < practical::MIN_SEARCH_LEAD { continue; }' in TRACE, 'lead must gate evaluation only')
need('self.practical_search_enabled = true;' in TRACE and 'pnp::request_release_resume();' in TRACE,
     'successful search must auto-enter WAIT')
need('self.practical_fail(1);' in TRACE and 'Do not guess/rebind' in TRACE,
     'rel40 mismatch must be a conservative retry')
need('lane_for_post' not in PRACTICAL, 'unsafe POST-only rebind present')
need('evaluate_post' not in PRACTICAL, 'unsafe POST-only evaluator present')
need('pub fn request_release_resume()' in HOOK, 'Rust release-resume wrapper missing')
need('host_request_release_resume' in BIND, 'release-resume binding missing')
need('static bool suicune_release_resume_pending = false;' in MAIN, 'C release gate missing')
need('const u32 release_block_keys = KEY_A | KEY_B | KEY_X | KEY_Y |' in MAIN, 'release key mask missing')
need('if ((held & release_block_keys) == 0)' in MAIN, 'release clear test missing')
need('FastValidate: hold UP and tap B' in MAIN, 'UP+B FastValidate path lost')
need('(just_pressed & KEY_B) && (held & KEY_DUP)' in MAIN, 'UP+B trigger lost')
need('(held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0' in MAIN,
     'fixed-window B/Y/X/L/R gate lost')
need('if (suicune_auto_resume_pending && !(held & KEY_DUP))' in MAIN,
     'UP safety during Exact-2F lost')
for marker in [
    'S660 WAIT', 'S660 READY UP+B', 'S660 RETRY B40 R>RESET',
    'S660 RETRY B716 R>RESET', 'S660 RETRY B717 R>RESET',
    'S660 RESET VC E', 'TRIAL,V660'
]:
    need(marker in TRACE, f'missing marker {marker}')


def arr(name):
    m = re.search(rf'const {name}: \[u32; 256\] = \[(.*?)\];', PRACTICAL, re.S)
    need(m is not None, f'missing array {name}')
    vals = [int(x) for x in re.findall(r'\d+', m.group(1))]
    need(len(vals) == 256, f'{name} length {len(vals)}')
    return vals


def lane_meta(i):
    m = re.search(rf'const L{i}: Lane = Lane \{{(.*?)\n\}};', PRACTICAL, re.S)
    need(m is not None, f'missing lane L{i}')
    s = m.group(1)
    out = {}
    for key in ['source','off40_a','off40_s','off716_a','off716_s','off717_a','off717_s']:
        mm = re.search(rf'{key}: (\d+)', s)
        need(mm is not None, f'L{i} missing {key}')
        out[key] = int(mm.group(1))
    return out


def apply_sums(state, sum_a, sum_s):
    add = state >> 8
    sub = state & 0xff
    total = add + sum_a
    return ((total & 0xff) << 8) | ((sub - (sum_s & 0xff) - ((total >> 8) & 0xff)) & 0xff)


def upd(state, a, s):
    add = state >> 8
    sub = state & 0xff
    z = add + a
    carry = 1 if z > 0xff else 0
    return ((z & 0xff) << 8) | ((sub - s - carry) & 0xff)


def guards(lane, state, div):
    md = lane_meta(lane)
    av, sv = (div >> 8) & 0xff, div & 0xff
    s40 = apply_sums(state, arr(f'L{lane}_P40_A')[av], arr(f'L{lane}_P40_S')[sv])
    d40 = (((av + md['off40_a']) & 0xff) << 8) | ((sv + md['off40_s']) & 0xff)
    s716 = apply_sums(state, arr(f'L{lane}_P716_A')[av], arr(f'L{lane}_P716_S')[sv])
    d716 = (((av + md['off716_a']) & 0xff) << 8) | ((sv + md['off716_s']) & 0xff)
    d717 = (((av + md['off717_a']) & 0xff) << 8) | ((sv + md['off717_s']) & 0xff)
    s717 = upd(s716, d717 >> 8, d717 & 0xff)
    return (s40,d40,s716,d716,s717,d717)

# Exact roots/guards from donor traces 0087,0094,0095,0089,0096,0086.
records = {
    1: (87, 0x6DC0, 0xF3F3, (0x8F84,0xEEEE,0x75D7,0x4949,0x78D4,0x0303)),
    2: (94, 0xA36D, 0xA5A5, (0x8F65,0x9292,0xCF75,0xEDED,0x76CD,0xA7A7)),
    3: (95, 0xAE4E, 0x0E0F, (0x756B,0xFBFB,0xCE67,0x5656,0xDE57,0x1010)),
    4: (89, 0xBDAC, 0xB0B0, (0x1D30,0x9797,0x473C,0xF2F2,0xF390,0xACAC)),
    5: (96, 0x21D7, 0xC3C3, (0x6B72,0xA9A9,0x1DF3,0x0404,0xDB35,0xBEBE)),
    6: (86, 0x636B, 0x5F5F, (0xCEE8,0x5A5A,0xD92B,0xB5B5,0x48BB,0x6F6F)),
}
for lane, (src, state, div, expected) in records.items():
    need(lane_meta(lane)['source'] == src, f'L{lane} source changed')
    need(guards(lane, state, div) == expected, f'L{lane} donor{src:04d} guard path drifted')

# Current counterexample 0098: PRE A/r10 selects L3 but actual C/r8 branch
# must fail at rel40. Target 00BC/4D4E, actual DDC6/3A3A.
g98 = guards(3, 0x00BC, 0x4D4E)
need((g98[0], g98[1]) != (0xDDC6, 0x3A3A), '0098 wrong branch would falsely pass rel40')

# Current counterexample 0100: PRE B/r11 selects L5 but actual C/r2 branch
# must also fail at rel40. Target 0CBB/CECE, actual C2EB/C0C0.
g100 = guards(5, 0x0CBB, 0xCECE)
need((g100[0], g100[1]) != (0xC2EB, 0xC0C0), '0100 wrong branch would falsely pass rel40')

print('Suicune v6.6.0 conservative branch-trial audit OK')
