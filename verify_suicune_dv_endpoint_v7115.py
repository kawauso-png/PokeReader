from pathlib import Path
import subprocess,sys
r=Path(__file__).resolve().parent
subprocess.run([sys.executable,'-B',str(r/'verify_suicune_shiny_gate_v7113.py')],check=True)
subprocess.run([sys.executable,'-B',str(r/'v7113/test_endpoint.py')],check=True)
assert (r/'v7113/dv_endpoint.h').read_bytes()==(r/'3gx/includes/dv_endpoint.h').read_bytes()
s=(r/'v7113/shadow.c').read_text();assert 'endpoint.mask==3' in s and 'finals>=3' not in s and 'r.error=109' not in s
s=(r/'v7113/gate_runtime.c').read_text();assert 'shiny7115_' in s and 'r->dv_write_mask,r->dv_write_frame' in s
s=(r/'3gx/sources/main.c').read_text();assert 'S7115 CPU TOO SLOW' in s
s=(r/'reader_core/src/crystal/trace.rs').read_text();assert 'S7114' not in s and 'S7115' in s
print('PASS v7115: qualified DV completion and diagnostic fields; physical input protection retained')
