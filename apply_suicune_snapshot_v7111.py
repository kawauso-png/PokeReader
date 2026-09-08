"""Apply after v7110; frozen native data capture only."""
from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
f=r/'reader_core/src/crystal/research.rs';s=f.read_text()
def replace(a,b):
    global s
    assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
replace('#[path="clock7110.rs"] mod clock7110;', '#[path="clock7110.rs"] mod clock7110;\n#[path="snapshot7111.rs"] mod snapshot7111;')
replace('        ACTIVE=PRE_OK;\n        // Persist','        if !snapshot7111::capture(target,PRE_OK && MODE==3) {PRE_OK=false;}\n        ACTIVE=PRE_OK;\n        // Persist')
replace('pub fn save() {\n    clock7110::save();','pub fn save() {\n    snapshot7111::save();\n    clock7110::save();')
f.write_text(s);shutil.copyfile(r/'v7111/snapshot.rs',r/'reader_core/src/crystal/snapshot7111.rs')
for path in ['3gx/sources/main.c','reader_core/src/crystal/trace.rs']:
    f=r/path;s=f.read_text().replace('S7110','S7111').replace('STALLPHASE,V7110,','STALLPHASE,V7111,')
    s=s.replace('S7111 CLOCK RECORD READY','S7111 STATE RECORD READY')
    f.write_text(s)
print('Applied v7111 frozen VC tables/state capture; physical UP, Exact2, M14 and clock hooks unchanged')
