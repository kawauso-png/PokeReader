from pathlib import Path

hook = Path('reader_core/src/crystal/hook.rs').read_text()
trace = Path('reader_core/src/crystal/trace.rs').read_text()
main = Path('3gx/sources/main.c').read_text()

start = hook.index('pub fn live_pass_observe_joymap')
next_pub = hook.find('\npub fn ', start + 10)
observer = hook[start: next_pub if next_pub > 0 else len(hook)]

must = [
    'let low_up = (joy[JOY_HJOYPAD_DOWN] & PAD_UP) != 0;',
    'if low_up {',
    'LIVE_PASS.exact2_up_advances = LIVE_PASS.exact2_up_advances.saturating_add(1);',
    'LIVE_PASS.exact2_up_advances == 2',
    'EXACT2_RELEASE_WAITING = true;',
    'pnp::request_pause();',
    'let hjoy = joy[JOY_HJOY_DOWN];',
]
for s in must:
    if s not in observer:
        raise SystemExit(f'v767i audit: missing observer token: {s}')

# FFA8 stays diagnostic; it must not be the Exact2 counter authority.
exact_block = observer[observer.index('// Count distinct RNG advances'):]
if 'if up {' in exact_block.split('if before_pass', 1)[0]:
    raise SystemExit('v767i audit: Exact2 still counts game-level FFA8')

for bad in ['gb_mem::write', 'host_write_mem', 'hid_up_mask_begin', 'RJOYP_ADDR =', 'RNG_ADVANCE =', 'ADIV =', 'SDIV =']:
    if bad in observer:
        raise SystemExit(f'v767i audit: forbidden Exact2 mutation: {bad}')

if 'hid_up_mask_begin()' in main:
    raise SystemExit('v767i audit: HID masking call remains in live main path')

if 'EXACT2,V767I' not in trace or 'polled_up_advances' not in trace:
    raise SystemExit('v767i audit: CSV lineage/header missing')
for marker in ['LIVEPASS,V767I', 'LIVEPASSHOST,V767I', 'JOYMAP,V767I', 'JOYFRAME,V767I']:
    if marker not in trace:
        raise SystemExit(f'v767i audit: missing lineage {marker}')

# JP joypad map remains read-only and rel40 remains diagnostic/non-terminal.
for addr in range(0xffa2, 0xffaa):
    if f'gb_mem::read_u8(0x{addr:04x})' not in trace:
        raise SystemExit(f'v767i audit: missing read-only joy address {addr:04X}')
if 'self.practical_active=false;\n                return' not in trace:
    raise SystemExit('v767i audit: rel40 non-terminal continuation missing')

print('AUDIT I PASS: FFA4 low-level poll is Exact2 authority; FFA8 remains diagnostic; no input/RNG/DIV writes')
