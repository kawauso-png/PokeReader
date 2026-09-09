from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'test'
    subprocess.run(['cc','-std=c11','-Wall','-Werror',str(r/'v7121_manual/test_manual.c'),'-o',str(p)],check=True)
    subprocess.run([str(p)],check=True)
s=(r/'3gx/sources/main.c').read_text()
assert s.index('if(manual7121_active && !gate7119_enabled())')<s.index('if(gate7119_enabled()){')
assert 'manual7121_active=false;manual7121_control.pending=0;' in s.split('int host7120_arm(void){')[1].split('void host7119_status')[0]
enter=s.split('static void manual7121_enter(void){')[1].split('\n}')[0]
for text in ['gate7113_cancel();','gate7119_disable();','rank7108_hunting=false;','suicune_root_lock_failed=true;','fixed_armed=false;']:
    assert text in enter
assert 'w[30]=7121' in (r/'3gx/sources/v7116_snapshot.c').read_text()
assert 'S7120' not in s
print('PASS: manual dispatch precedes legacy hunt; movement cancels old arm; S7121 snapshot tag')

with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'runtime'
    subprocess.run(['cc','-std=c11','-O2','-I'+str(r/'v7116'),'-I'+str(r/'3gx/includes'),str(r/'v7121_manual/test_runtime.c'),'-o',str(p)],check=True)
    subprocess.run([str(p),str(Path(d)/'report.json')],check=True)
print('PASS: explicit opcode2 calibration allows ordinary DVs including 0000; shiny opcode1 still rejects them')
