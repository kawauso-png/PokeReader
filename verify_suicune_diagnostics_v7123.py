from pathlib import Path
import tempfile,subprocess
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'events'
 subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(r/'v7123_diagnostics'),str(r/'v7123_diagnostics/test_events.c'),'-o',str(p)],check=True)
 subprocess.run([str(p)],check=True)
 # Re-run all request guards against the actual generated request runtime.
 base=(r/'v7122_calibration/test_runtime.c').read_text()
 generated=(r/'3gx/sources/v7113_gate_runtime.c').read_text()
 start=generated.index('/* Bounded neutral frame calibration.')
 end=generated.index('/* Independent terminal record:',start)
 runtime=generated[start:end]
 (Path(d)/'runtime.inc').write_text('static void gate7123_begin(void){}\n'+runtime)
 (Path(d)/'test.c').write_text(base)
 subprocess.run(['cc','-std=c11','-O2','-I'+str(r/'v7116'),'-I'+str(r/'3gx/includes'),str(Path(d)/'test.c'),'-o',str(Path(d)/'guards')],check=True)
 subprocess.run([str(Path(d)/'guards'),str(Path(d)/'report.json')],check=True)
s=(r/'3gx/sources/main.c').read_text()
assert 'seconds>5?' not in s
assert 'now>target+2681118ULL' in s
assert 'gate7123_finish((just_pressed & KEY_SELECT)?11:10,now,held,0);' in s
assert 'w[30]=7123' in (r/'3gx/sources/v7116_snapshot.c').read_text()
print('PASS: S7123 log hooks, early-UP cue and unchanged timing guard')
