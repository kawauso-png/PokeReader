from pathlib import Path

H = Path('reader_core/src/crystal/hook.rs').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()
C = Path('3gx/sources/main.c').read_text()
P = Path('3gx/includes/pokereader.h').read_text()
L = Path('reader_core/src/lib.rs').read_text()

errors=[]
def need(cond,msg):
    if not cond: errors.append(msg)

# Closed-loop source and actuator.
need('JOY_HJOY_DOWN: usize = 6' in H,'FFA8 authoritative hJoyDown missing')
need('LIVE_PASS.exact2_up_advances' in H,'Exact2 accepted-UP counter missing')
need('LIVE_PASS.exact2_up_advances == 2' in H,'second accepted-UP pause boundary missing')
need('pnp::request_pause();' in H,'Pause actuator missing at Exact2 boundary')
need('EXACT2_RELEASE_WAITING = true;' in H,'physical-release checkpoint missing')
need('suicune_exact2_release_waiting()' in C,'pause loop release checkpoint missing')
need('(held & KEY_DUP) == 0' in C,'physical UP release not required')
need('suicune_exact2_release_confirmed();' in C,'release confirmation missing')
need('suicune_exact2_release_waiting();' in P and 'suicune_exact2_release_confirmed();' in P,'C ABI declarations missing')
need('pub extern "C" fn suicune_exact2_release_waiting()' in L,'Rust release-wait ABI missing')

# v7.6.8 must stop extra FFA2..FFA9 reads after the first clear following release.
need('pub fn exact2_needs_joymap_sample()' in H,'dynamic joymap gate missing')
need('LIVE_PASS.exact2_first_clear_advance == 0' in H,'joymap gate does not wait for post-release clear')
need('if exact2_needs_joymap_sample()' in T,'trace does not use dynamic joymap gate')
need('gb_mem::read_u8(0xffa2)' in T and 'gb_mem::read_u8(0xffa9)' in T,'FFA2..FFA9 observation missing')

# Exact2 validation at rel40: exactly two consecutive Crystal-accepted UP advances.
need('lp.exact2_up_advances == 2' in T,'rel40 Exact2 count validation missing')
need('lp.exact2_second_up_advance == lp.exact2_first_up_advance.wrapping_add(1)' in T,'consecutive Exact2 validation missing')
need('lp.exact2_release_confirmed != 0' in T,'release confirmation not validated')
need('lp.exact2_first_clear_advance != 0' in T,'post-release clear not validated')
need('self.practical_fail(15);return' in T,'bad Exact2 fast-abort missing')

# rel40 actual POST/State/DIV inverse gate and shiny continuation.
need('evaluate_actual_post_inverse_v763' in T,'rel40 inverse evaluation missing')
need('if let Some(pred)=g.prediction' in T,'shiny-compatible continuation missing')
need('self.rebind_practical_post_v690(pred,post.proto,post.rot40);' in T,'actual POST rebind missing')
need('self.practical_fail(14);return' in T,'rel40 nonshiny fast-abort missing')

# Downstream native verification remains active.
need('if rel==716&&!self.practical_checked716' in T,'rel716 verification missing')
need('else if rel==717&&!self.practical_checked717' in T,'rel717 verification missing')
need('self.endpoint.stop2_advance = current.advance;' in T,'stop2 detector missing')
need('self.endpoint.expected_dv_advance = current.advance.wrapping_add(13);' in T,'stop2 -> DV +13 model missing')
need('if self.probe_active && window[2] == SUICUNE_SPECIES' in T,'native Suicune DV detector missing')

# Final lineage and operator guidance.
need('EXACT2,V768' in T,'V768 Exact2 CSV missing')
need('JOYMAP,V768' in T and 'JOYFRAME,V768' in T,'V768 joypad CSV missing')
need('INPUTLAB,V768' in T and 'INPUTHOST,V768' in T,'V768 input summary CSV missing')
need('S768 EXACT2 ACCEPTED' in T and 'RELEASE UP' in T,'release-UP UI missing')
need('S768 SHINY INTEGRATED' in T,'integrated scan title missing')

# Mutation boundary: controller may observe and Pause/Resume only.
need('gb_mem::write' not in T,'trace writes GB RAM')
need('pnp::write' not in H,'hook writes process/game memory')
need('hid_mask_up_begin()' not in H,'HID mask begin remains active')
need('0xff00' not in T and 'FF00' not in T,'trace contains rJOYP substitution path')

# Isolate exact2 controller path so pre-existing unrelated declarations do not
# cause false positives.
def between(src,a,b):
    i=src.find(a); j=src.find(b,i+len(a)) if i>=0 else -1
    return src[i:j] if i>=0 and j>=0 else ''
controller = between(H,'pub fn live_pass_observe_joymap','pub fn live_pass_telemetry')
need(controller!='','cannot isolate closed-loop controller')
for bad,label in [
    ('RNG_ADVANCE =','RNG advance write'),('ADIV =','ADIV write'),('SDIV =','SDIV write'),
    ('gb_mem::write','GB memory write'),('| KEY_DUP','synthetic UP'),('pnp::write','process/game write'),
    ('0xff00','rJOYP substitution')]:
    need(bad not in controller,'controller contains '+label)

if errors:
    print('AUDIT FAIL v7.6.8')
    for e in errors: print(' -',e)
    raise SystemExit(1)

print('AUDIT PASS v7.6.8: Crystal FFA8 closed-loop Exact2 uses observation + Pause/Resume only')
print('AUDIT PASS v7.6.8: no HID/rJOYP/GB-RAM/RNG/DIV/DV substitution')
print('AUDIT PASS v7.6.8: rel40 nonshiny abort / shiny continue -> 716/717 -> stop2 -> native DV')
