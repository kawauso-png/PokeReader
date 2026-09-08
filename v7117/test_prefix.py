from pathlib import Path
import subprocess,tempfile,json
r=Path(__file__).resolve().parent;cases=json.loads((r/'prefix_fixtures.json').read_text())
src='#include "prefix.h"\n#include <assert.h>\n#include <stdio.h>\nint main(void){\n'
for c in cases:src+=f'assert(prefix7117_offers({c["seed"]},{c["phase"]})=={c["offers"]});\n'
src+='printf("PASS: independent prefix-sum fixtures, including the held-out natural shiny PRE\\n");return 0;}\n'
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.c').write_text(src);subprocess.run(['cc','-O2','-I'+str(r),str(p/'test.c'),str(r/'prefix.c'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
