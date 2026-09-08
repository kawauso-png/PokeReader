"""Apply after v7115: guarded fast blocks and automatic complete predictor input."""
from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
for name in ['shadow.c','gate_runtime.c']:shutil.copyfile(r/'v7116'/name,r/'3gx/sources'/('v7113_'+name))
shutil.copyfile(r/'v7116/snapshot.c',r/'3gx/sources/v7116_snapshot.c')
for name in ['snapshot.h','shadow.h','const_core.h','fast_dispatch.h']:shutil.copyfile(r/'v7116'/name,r/'3gx/includes'/name)
for name in ['3gx/sources/main.c','reader_core/src/crystal/trace.rs']:
 p=r/name;s=p.read_text();assert 'S7115' in s;s=s.replace('S7115','S7116').replace('STALLPHASE,V7115,','STALLPHASE,V7116,');p.write_text(s)
print('Applied v7116: guarded exact instruction blocks and latest complete input snapshot; physical input and candidate criteria retained')
