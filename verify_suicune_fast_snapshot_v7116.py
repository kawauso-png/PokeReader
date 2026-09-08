from pathlib import Path
import subprocess,sys,tempfile,shutil
r=Path(__file__).resolve().parent
for name in ['generate_fast.py','test_snapshot.py','test_gate_runtime.py','test_dispatch.py']:
 args=[sys.executable,'-B',str(r/'v7116'/name)]+(['--check'] if name=='generate_fast.py' else [])
 subprocess.run(args,check=True)
with tempfile.TemporaryDirectory() as td:
 d=Path(td)
 for name in ['test_endpoint.py','arm_core.c','arm_core.h','shadow.h','dv_endpoint.h']:shutil.copyfile(r/'v7113'/name,d/name)
 for name in ['shadow.c','shadow.h','fast_dispatch.h','const_core.h']:shutil.copyfile(r/'v7116'/name,d/name)
 subprocess.run([sys.executable,'-B',str(d/'test_endpoint.py')],check=True)
for name in ['shadow.c','gate_runtime.c']:assert (r/'v7116'/name).read_bytes()==(r/'3gx/sources'/('v7113_'+name)).read_bytes()
assert (r/'v7116/snapshot.c').read_bytes()==(r/'3gx/sources/v7116_snapshot.c').read_bytes()
for name in ['snapshot.h','shadow.h','const_core.h','fast_dispatch.h']:assert (r/'v7116'/name).read_bytes()==(r/'3gx/includes'/name).read_bytes()
s=(r/'3gx/sources/main.c').read_text();assert 'S7116' in s and 'S7115' not in s
s=(r/'v7116/shadow.c').read_text();assert 'int fast_enabled=code_guard();' in s and 'if(fast_enabled&&fast_step())' in s and 'endpoint.mask==3' in s
s=(r/'v7116/gate_runtime.c').read_text();assert s.index('snapshot7116_save(')<s.index('for(profile=0;profile<2;profile++)') and 'GATE7116_PRE' in s
print('PASS: v7116 integration, exact fallback, snapshot before mutation, physical input/endpoint retained')
