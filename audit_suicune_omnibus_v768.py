from pathlib import Path
import re

h = Path('reader_core/src/crystal/hook.rs').read_text()
t = Path('reader_core/src/crystal/trace.rs').read_text()

checks = []
def ok(cond, msg):
    if not cond:
        raise SystemExit('AUDIT V768 FAIL: ' + msg)
    checks.append(msg)

ok('const LIVE_SAMPLE_CAP: usize = 48;' in h, '48-advance sample horizon')
ok('const LIVE_RJOYP_EVENT_CAP: usize = 128;' in h, '128 rJOYP events')
ok('for addr in 0u32..=0x3fff' in h and 'v1 == 0xff' in h and 'v2 == 0xff' in h, 'neutral source is verified 0xFF in fixed ROM0')
ok('fn gb_read_mem(regs: &mut [u32]' in h, 'GB read hook can redirect r0')
ok('let requested = regs[0];\n    live_pass_filter_rjoy(regs);' in h, 'original request retained before redirect')
ok('regs[0] = LIVE_PASS.neutral_addr as u32;' in h, 'masked rJOYP redirects only effective address')
ok('let in_pass = pass_delta < LIVE_PASS_FRAMES;' in h and 'if in_pass {' in h, '2-advance pass window retained')
ok('LIVE_PASS.passthrough_rjoy_reads' in h and 'LIVE_PASS.redirected_rjoy_reads' in h, 'redirect/pass counters')
ok('post_delta < LIVE_POST_FRAMES' in h, 'summary remask restricted to first 4 advances')
ok('LIVE_PASS.first_input_advance.wrapping_add(LIVE_SAMPLE_CAP as u32 - 1)' in h, 'old 22-advance auto-stop replaced by rel40-safe fallback')
ok('hid_mask_up_begin' not in h and 'hid_mask_up_restore' not in h and 'hid_mask_capable' not in h and 'hid_mask_stats' not in h, 'no HID shared-memory mask calls in generated hook')
live = h[h.index('// ---- v7.6.7 continuous physical-UP HID mask probe'):h.index('// Suicune VBlank Context')]
ok('pnp::write(' not in live, 'no pnp write in live-pass block')
ok('gb_mem::read_u8(addr)' in h and 'gb_mem::write' not in h, 'ROM source read-only; no GB write API')
ok(all(f'gb_mem::read_u8(0xffa{x})' in t for x in range(2,10)), 'JP FFA2-FFA9 read-only joy map')
ok('gb_mem::read_u8(0xff9a)' not in t, 'obsolete FF9A verifier absent')
ok('for i in 0..n.min(48)' in t, '48 raw JOYFRAME rows exportable')
ok('OMNI,V768' in t and 'RJOYPEVENT,V768' in t and 'LIVEPASS,V768' in t and 'JOYFRAME,V768' in t, 'V768 lineage on new telemetry')
ok('if rel==40&&!self.practical_checked40' in t and 'evaluate_actual_post_inverse_v763' in t and 'self.practical_fail(13);return' in t, 'existing actual rel40 POST/inverse gate retained')
ok('RNG_ADVANCE =' not in live, 'live-pass block does not rewrite RNG advance')
assigns = re.findall(r'regs\[0\]\s*=\s*([^;]+);', live)
ok(assigns == ['LIVE_PASS.neutral_addr as u32'], 'only r0 mutation is neutral-address redirect')

# CSV schema guard: after Python generation the Rust multiline string contains
# real newlines, so inspect the actual generated OMNI data line directly.
omni_start = t.index('OMNI,V768,')
omni_fmt = t[omni_start:].splitlines()[0]
ok(omni_fmt.count('{') == 22 and omni_fmt.count('}') == 22, 'OMNI format has exactly 22 placeholders')
expected_omni = 'OMNI,V768,{:04X},{:02X},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{},{},{},{},{},{},{}'
ok(omni_fmt == expected_omni, 'OMNI placeholder types/order match 22-column schema')

print('AUDIT V768 PASS: ' + '; '.join(checks))
