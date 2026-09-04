from pathlib import Path

H = Path('reader_core/src/crystal/hook.rs').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()
C = Path('3gx/sources/main.c').read_text()
P = Path('3gx/includes/pokereader.h').read_text()
L = Path('reader_core/src/lib.rs').read_text()

checks = []
def ok(cond, msg):
    if not cond:
        raise SystemExit('AUDIT H FAIL: ' + msg)
    checks.append(msg)

ok('const LIVE_SAMPLE_CAP: usize = 96;' in H, '96-frame joymap cap')
ok('gb_mem::read_u8(0xffa2)' in T and 'gb_mem::read_u8(0xffa9)' in T, 'JP FFA2-FFA9 read-only observation')
ok('gb_mem::write' not in T, 'no GB RAM write in trace')
ok('pnp::write' not in H, 'no process/game write in live hook')
ok('hid_mask_up_begin()' not in H, 'no HID mask begin in generated hook')
ok('FF00' not in T and '0xff00' not in T, 'no FF00 return substitution in trace')
ok('EXACT2,V767H' in T, 'V767H Exact2 CSV lineage')
ok('LIVEPASS,V767H' in T and 'JOYMAP,V767H' in T and 'JOYFRAME,V767H' in T, 'all V767H telemetry lineages')
ok('LIVEPASS,V767G' not in T and 'V767F' not in T, 'no stale g/f lineage in final trace')
ok('LIVE_SAMPLE_CAP' in H and 'JOY_HJOY_DOWN: usize = 6' in H, 'FFA8 authoritative hJoyDown')
ok('LIVE_PASS.exact2_up_advances' in H, 'game-accepted UP distinct-advance counter')
ok('LIVE_PASS.exact2_up_advances == 2' in H, 'pause exactly on second accepted UP advance')
ok('pnp::request_pause();' in H, 'request Pause at Exact2 boundary')
ok('EXACT2_RELEASE_WAITING = true;' in H, 'release checkpoint armed after second accepted UP')
ok('suicune_exact2_release_waiting()' in C, 'C pause loop reads release checkpoint')
ok('(held & KEY_DUP) == 0' in C, 'physical UP release required before resume')
ok('suicune_exact2_release_confirmed();' in C, 'release confirmation handshake')
ok('is_paused = false;' in C, 'resume only through existing host pause state')
ok('suicune_exact2_release_waiting();' in P and 'suicune_exact2_release_confirmed();' in P, 'C ABI declarations')
ok('pub extern "C" fn suicune_exact2_release_waiting()' in L, 'Rust C ABI release-wait export')
ok('pub extern "C" fn suicune_exact2_release_confirmed()' in L, 'Rust C ABI release-confirm export')
ok('if self.probe_session && live_pass_should_finish()' not in T, 'old +22 diagnostic auto-stop removed')
ok('for i in 0..n.min(96)' in T, 'raw joymap exports through rel40 neighborhood')

# Scope mutation checks to code introduced/used by the v7.6.7h controller,
# rather than matching pre-existing static declarations elsewhere in hook.rs.
def slice_between(src, start, end, label):
    a = src.find(start)
    b = src.find(end, a + len(start)) if a >= 0 else -1
    if a < 0 or b < 0:
        raise SystemExit('AUDIT H FAIL: cannot isolate ' + label)
    return src[a:b]

observer = slice_between(
    H,
    'pub fn live_pass_observe_joymap',
    'pub fn live_pass_telemetry',
    'joymap/exact2 observer path',
)
handshake = slice_between(
    H,
    'pub fn exact2_release_waiting',
    'pub fn live_pass_telemetry',
    'release handshake path',
)
control = observer + handshake

for forbidden, label in [
    ('RNG_ADVANCE =', 'RNG advance assignment'),
    ('ADIV =', 'ADIV assignment'),
    ('SDIV =', 'SDIV assignment'),
    ('gb_mem::write', 'GB memory write'),
    ('| KEY_DUP', 'synthetic physical UP'),
    ('pnp::write', 'process/game write'),
]:
    ok(forbidden not in control, 'no ' + label + ' in closed-loop control path')

ok('0xff00' not in control and 'FF00' not in control, 'no rJOYP substitution in controller')
ok('joy[JOY_HJOY_DOWN]' in observer, 'Exact2 decision comes from observed FFA8')
ok('pnp::request_pause();' in observer, 'controller actuator is Pause only')

# Omnibus requirement: rel40 is diagnostic, never the terminal condition.
rel40_anchor = 'let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);'
a = T.find(rel40_anchor)
if a < 0:
    raise SystemExit('AUDIT H FAIL: rel40 inverse evaluation missing')
b = T.find('\n            }', a)
if b < 0:
    raise SystemExit('AUDIT H FAIL: cannot isolate rel40 block')
rel40 = T[a:b]
ok('self.v763_gate_models=g.models' in rel40 and 'self.v763_gate_evaluated=g.evaluated' in rel40, 'rel40 inverse telemetry retained')
ok('self.practical_active=false;' in rel40, 'rel40 hands control back to generic native trace')
for term in ['self.practical_fail(10)', 'self.practical_fail(11)', 'self.practical_fail(12)', 'self.practical_fail(13)']:
    ok(term not in rel40, 'rel40 has no terminal ' + term)
ok('if !post.valid||post.best_score!=0{self.practical_miss=12;self.practical_active=false;return}' in T, 'POST-classification miss is non-terminal')
ok('if self.probe_active && window[2] == SUICUNE_SPECIES' in T, 'generic native Suicune result detector remains active')
ok('self.probe_active = false;' in T, 'generic result path owns final probe stop')

print('AUDIT H PASS: closed-loop Exact2 uses observation + Pause/Resume + physical UP release only')
print('AUDIT H PASS: no HID/FF00/GB-RAM/RNG/DIV/DV input or state substitution')
print('AUDIT H PASS: rel40 is diagnostic/non-terminal and native Suicune final DV remains observable')
