from pathlib import Path

main = Path('3gx/sources/main.c').read_text()
hook = Path('reader_core/src/crystal/hook.rs').read_text()
trace = Path('reader_core/src/crystal/trace.rs').read_text()

errors=[]
def need(cond,msg):
    if not cond: errors.append(msg)

stage_start=main.find('if (suicune_wait_up_after_b)')
stage_end=main.find('// Y+L schedules', stage_start)
stage=main[stage_start:stage_end] if stage_start>=0 and stage_end>stage_start else ''
need(stage!='','stage2 block not found')
need('fixed_a_frames = 2;' in stage,'stage2 does not force Exact2F')
need('fixed_run_pending = true;' in stage,'stage2 does not queue fixed scheduler')
need('suicune_auto_resume_pending = true;' in stage,'stage2 does not queue release->resume')
need('is_paused = false;' not in stage,'stage2 bypasses Exact2F by direct resume')
need('KEY_DUP' in stage,'stage2 does not require physical UP')

# No runtime HID mutation in the generated execution path.
need('hid_up_mask_begin(' not in main,'C main still calls HID mask begin')
need('hid_up_mask_restore(' not in main,'C main still calls HID mask restore')
need('hid_mask_up_begin()' not in hook,'Rust hook still calls HID mask begin')
need('hid_mask_up_restore()' not in hook,'Rust hook still calls HID mask restore')

# No GB input/RNG/DIV writes were added by the integrated trace path.
need('gb_mem::write' not in trace,'trace writes GB memory')
need('0xffa2' in trace and '0xffa9' in trace,'JP joypad chain FFA2..FFA9 missing')
need('live_pass_needs_joymap_sample()' in trace,'bounded joy sampling gate missing')
need('const LIVE_SAMPLE_CAP: usize = 8;' in hook,'input sample cap is not 8 advances')
need('live_pass_should_finish()' not in trace,'old 22-advance early-stop is still active')

# rJOYP is observed only; no returned-value/address substitution.
need('RJOYP_ADDR: u32 = 0xff00' in hook,'rJOYP address probe missing')
need('RJOYFRAME,V768' in trace,'rJOYP timing CSV missing')
need('regs[0]' not in hook[hook.find('fn live_pass_filter_rjoy'):hook.find('// Suicune VBlank Context',hook.find('fn live_pass_filter_rjoy'))],
     'rJOYP observer redirects read address')

# Exact2F must be verified by Crystal's FFA8, not host state alone.
need('JOY_HJOY_DOWN' in hook and 'JOY_HJOY_DOWN: usize = 6' in hook,'FFA8 authoritative index missing')
need('lp.game_pass_observed_advances != 2' in trace,'Exact2F observed-count gate missing')
need('lp.game_pass_up_advances != 2' in trace,'Exact2F FFA8-UP gate missing')
need('lp.game_remask_up_advances != 0' in trace,'post-release FFA8-clear gate missing')

# rel40 gate must abort nonshiny, but continue a surviving shiny prediction.
need('evaluate_actual_post_inverse_v763' in trace,'rel40 inverse evaluation missing')
need('if let Some(pred)=g.prediction' in trace,'rel40 shiny continuation missing')
need('self.rebind_practical_post_v690(pred,post.proto,post.rot40);' in trace,'actual POST rebind missing')
need('self.practical_fail(14);return' in trace,'rel40 nonshiny abort missing')
need('self.practical_fail(15);return' in trace,'input failure abort missing')

# Strict downstream verification and natural endpoint/DV capture remain present.
need('if rel==716&&!self.practical_checked716' in trace,'rel716 verification missing')
need('else if rel==717&&!self.practical_checked717' in trace,'rel717 verification missing')
need('self.endpoint.stop2_advance = current.advance;' in trace,'stop2 detector missing')
need('self.endpoint.expected_dv_advance = current.advance.wrapping_add(13);' in trace,'stop2->DV +13 detector missing')
need('if self.probe_active && window[2] == SUICUNE_SPECIES' in trace,'native Suicune DV detector missing')
need('INTEGRATED,V768' in trace,'integrated verdict CSV missing')
need('JOYFRAME,V768' in trace,'joy frame CSV lineage missing')
need('INPUTLAB,V768' in trace,'input telemetry lineage missing')

# No synthetic UP assignment patterns.
for bad in ('|= KEY_DUP','= KEY_DUP;','KEY_DUP | KEY_DUP'):
    need(bad not in stage, f'synthetic UP pattern in stage2: {bad}')

if errors:
    print('AUDIT FAIL v7.6.8')
    for e in errors: print(' -',e)
    raise SystemExit(1)

print('AUDIT PASS v7.6.8: natural physical-UP Exact2F uses pause/frame control only')
print('AUDIT PASS v7.6.8: JP FFA2-FFA9 + bounded rJOYP timing observed read-only')
print('AUDIT PASS v7.6.8: rel40 nonshiny abort / shiny continue -> 716/717 -> stop2 -> native DV')
