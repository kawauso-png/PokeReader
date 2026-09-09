from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'3gx/sources/v7113_gate_runtime.c';s=p.read_text();old=(r/'v7121_manual/runtime.inc').read_text();assert s.count(old)==1
s=s.replace(old,(r/'v7122_calibration/runtime.inc').read_text());p.write_text(s)
p=r/'3gx/sources/v7116_snapshot.c';s=p.read_text();assert 'w[30]=7121' in s
s=s.replace('w[30]=7121','w[30]=7122').replace('\\"software\\":7121','\\"software\\":7122');p.write_text(s)
p=r/'3gx/sources/main.c';s=p.read_text().replace('S7121','S7122');p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text().replace('S7121','S7122').replace('STALLPHASE,V7121,','STALLPHASE,V7122,');p.write_text(s)
p=r/'3gx/PokeReader.plgInfo';s=p.read_text();assert 'Revision: 21' in s;p.write_text(s.replace('Revision: 21','Revision: 22'))
print('Applied S7122: calibration retains actual BEFORE and tolerates native static changes; shiny arm stays strict')
