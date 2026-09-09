from pathlib import Path
import tempfile,subprocess
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'runtime'
 subprocess.run(['cc','-std=c11','-O2','-I'+str(r/'v7116'),'-I'+str(r/'3gx/includes'),str(r/'v7122_calibration/test_runtime.c'),'-o',str(p)],check=True)
 subprocess.run([str(p),str(Path(d)/'report.json')],check=True)
assert (r/'v7122_calibration/runtime.inc').read_text() in (r/'3gx/sources/v7113_gate_runtime.c').read_text()
assert 'w[30]=7122' in (r/'3gx/sources/v7116_snapshot.c').read_text()
print('PASS: ordinary calibration measures static drift; code/heap/ROM changes reject; shiny static change still rejects')
