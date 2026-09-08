from pathlib import Path
import sys,tempfile,subprocess,json,os
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r/'v7111'))
from extract_snapshot import parse
assert (r/'reader_core/src/crystal/snapshot7111.rs').read_bytes()==(r/'v7111/snapshot.rs').read_bytes()
research=(r/'reader_core/src/crystal/research.rs').read_text()
assert research.count('snapshot7111::capture(target,PRE_OK && MODE==3)')==1
assert research.count('snapshot7111::save();')==1
assert 'S7111 STATE RECORD READY' in (r/'3gx/sources/main.c').read_text()
assert 'MemorySize: 10MiB' in (r/'3gx/PokeReader.plgInfo').read_text()
# Snapshot capture must not be invoked in any live observation hook.
for name in ('hook.rs','clock7110.rs'):assert 'snapshot7111' not in (r/'reader_core/src/crystal'/name).read_text()
source=(r/'v7111/snapshot.rs').read_text()
for token in ('write_volatile','request_resume','gb_mem::write','trace_file_open'):assert token not in source
with tempfile.TemporaryDirectory() as td:
    d=Path(td);t=(r/'v7111/test_snapshot.rs.in').read_text().replace('SNAPSHOT_PATH',json.dumps(str(r/'v7111/snapshot.rs')))
    (d/'test.rs').write_text(t)
    subprocess.run(['rustc','--edition=2021','--test',str(d/'test.rs'),'-o',str(d/'test')],check=True)
    subprocess.run([str(d/'test'),'--test-threads=1'],check=True,env={**os.environ,'SNAPSHOT_TEST_OUT':str(d/'good.csv')})
    meta,blocks=parse(d/'good.csv');assert len(blocks)==7 and meta['target']==1144
    original=(d/'good.csv').read_text()
    # Reject truncation, duplicate records, data corruption, invalid captures.
    for name,bad in [('truncated',original.rsplit('R7111_SNAPSHOT_END',1)[0]),
      ('duplicate',original+next(s for s in original.splitlines() if s.startswith('R7111_DATA,'))+'\n'),
      ('corrupt',original.replace('0001020304050607','0101020304050607',1)),
      ('invalid',original.replace(',1144,1,',',1144,0,',1))]:
        f=d/(name+'.csv');f.write_text(bad)
        try:parse(f)
        except ValueError:pass
        else:raise AssertionError(name)
print('PASS: bounded frozen pages, required IO tables, state stability, parser integrity and no live-hook capture')
