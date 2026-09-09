from pathlib import Path
import subprocess,tempfile,json
r=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as td:
 t=Path(td)
 subprocess.run(['cc','-std=c11','-O2','-Wall','-Wno-unused-function','-Wno-unused-variable','-I'+str(r/'v7116'),'-I'+str(r/'v7120_mac'),'-I'+str(r/'3gx/includes'),str(r/'v7120_mac/test_runtime.c'),'-o',str(t/'test')],check=True)
 subprocess.run([str(t/'test'),str(t/'report.json')],check=True)
 s=json.loads((t/'report.json').read_text());assert s['completed_frames']==32 and s['sample_count']==33 and len(s['samples'])==33 and s['sample_log_bytes']==33*56
s=(r/'3gx/sources/main.c').read_text();assert s.count('if(gate7119_poll(held))break;')==1 and 'int host7120_arm(void)' in s and 'S7119' not in s
runtime=(r/'3gx/sources/v7113_gate_runtime.c').read_text();assert (r/'v7120_mac/runtime.inc').read_text() in runtime
s=(r/'3gx/sources/v7116_snapshot.c').read_text();assert 'w[30]=7120' in s and 'mac_samples.bin' in s
print('PASS: generated integration, full sample binary layout, version tags')

arm=s if False else (r/"3gx/sources/main.c").read_text().split("int host7120_arm(void){",1)[1].split("void host7119_status",1)[0]
assert "suicune_root_lock_ready=true;" in arm and "suicune_neutral_probe_pending=false;" in arm
