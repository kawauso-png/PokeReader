from pathlib import Path
import subprocess,sys,json
r=Path(__file__).resolve().parent
for name in ['test_prefix.py','test_gate_runtime.py']:subprocess.run([sys.executable,'-B',str(r/'v7117'/name)],check=True)
for name,target in [('gate_runtime.c','v7113_gate_runtime.c'),('snapshot.c','v7116_snapshot.c'),('prefix.c','v7117_prefix.c')]:assert (r/'v7117'/name).read_bytes()==(r/'3gx/sources'/target).read_bytes()
for name in ['prefix.h','prefix_data.h']:assert (r/'v7117'/name).read_bytes()==(r/'3gx/includes'/name).read_bytes()
s=(r/'v7117/gate_runtime.c').read_text();assert 'rank7108_evaluate()' not in s and 'rank7108_best_rank()' not in s and 'suicune_native_pre_state' in s
assert 'if(!prefix_models&&(checks&63U)!=0)return 0;' in s and 'shadow7113_run(&pre,65)' in s and 'shadow7113_run(&in,1100)' in s
assert 'selected&&committed&&target==advance&&state==seed' in s
s=(r/'3gx/sources/main.c').read_text();assert 'S7117' in s and 'S7116' not in s
assert 'suicune_neutral_probe_frames=(gate7113_checks()&63U)?2U:3U;' in s and 'suicune_neutral_probe_remaining=suicune_neutral_probe_frames;' in s
assert 'gate7117_progress_stage?"PRE":"FULL"' in s and 'SPEED TEST FRAME' in s
assert 'if ((held & neutral_block) != 0)' in s and 'suicune_neutral_probe_remaining--;' in s
s=(r/'reader_core/src/crystal/research.rs').read_text();assert 'PRE_OK=PRE_OK && (native_checked || legacy_checked);' in s and 'gate7117_selected_pre(target,actual as u32)' in s
s=(r/'reader_core/src/crystal/trace.rs').read_text();assert 'pub fn native_pre_state' in s and 'self.probe_session || pnp::current_keys()!=0' in s and 'V797_FORCE_FINAL_DV_VALIDATION' in s
for f,text in [('reader_core/src/lib.rs','crystal::native_pre_state(advance)'),('reader_core/src/crystal/frame.rs','state.trace.native_pre_state(&reader)'),('reader_core/src/crystal/mod.rs','pub use frame::native_pre_state;')]:assert text in (r/f).read_text()
m=json.loads((r/'v7117/prefix_model.json').read_text());assert m['models']==195 and m['phase_bytes']==532272
print('PASS: broad PRE bridge, committed collector exception, neutral stepping, held-out proposal and full-DV-only selection')
