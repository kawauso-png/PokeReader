from pathlib import Path
import subprocess,sys
r=Path(__file__).resolve().parent
subprocess.run([sys.executable,'-B',str(r/'verify_suicune_shiny_gate_v7113.py')],check=True)
s=(r/'reader_core/src/crystal/trace.rs').read_text()
for text in ['S7111','S7112','S7113','B -> RELEASE; WAIT -> UP']:assert text not in s
assert 'WAIT FOR TRY SHINY DV' in s and 'ADV{} NEUTRAL{}F' in s
s=(r/'3gx/sources/main.c').read_text();assert 'S7114 CPU TOO SLOW' in s
s=(r/'v7113/gate_runtime.c').read_text();assert 'if(seconds>900)' in s and 'GATE7114_BENCH' in s and 'GATE7114_CPU' in s
s=(r/'v7113/shadow.c').read_text();assert 'shadow_arm_inline(&cpu,readmem,writemem)' in s and 'always_inline' in s
print('PASS v7114 speed guard retained, expanded diagnostics, old UI guidance removed, specialized interpreter')
