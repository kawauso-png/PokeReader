"""Validate frozen page records and extract known memory for native replay."""
from pathlib import Path
import csv,json,hashlib,argparse,io
PAGE=4096;STATIC_PAGES=0x14f;PAGES=STATIC_PAGES+256
def fnv(b):
    h=2166136261
    for v in b:h=((h^v)*16777619)&0xffffffff
    return h
def parse(path):
    meta=None;end=None;pages={};chunks={}
    raw=path.read_bytes()
    if any(not line.startswith(b'BUCKET738,') for line in raw.splitlines() if b'\0' in line):
        raise ValueError('NUL outside legacy BUCKET738 field')
    with io.StringIO(raw.replace(b'\0',b'').decode()) as f:
        for row in csv.reader(f):
            if not row:continue
            if row[0]=='R7111_SNAPSHOT':
                if meta is not None or len(row)!=9:raise ValueError('duplicate/bad snapshot header')
                meta=dict(version=int(row[1]),target=int(row[2]),valid=int(row[3]),heap=int(row[4],16),total=int(row[5]),present=int(row[6]),page=int(row[7]))
            elif row[0]=='R7111_PAGE':
                if len(row)!=5:raise ValueError('bad page header')
                i=int(row[1])
                if i in pages:raise ValueError('duplicate page')
                pages[i]=(int(row[2],16),int(row[3]),int(row[4],16))
            elif row[0]=='R7111_DATA':
                if len(row)!=4:raise ValueError('bad data row')
                i,off=int(row[1]),int(row[2]);b=bytes.fromhex(row[3])
                if (i,off) in chunks or len(b)!=512 or off not in range(0,PAGE,512):raise ValueError('duplicate/bad data chunk')
                chunks[i,off]=b
            elif row[0]=='R7111_SNAPSHOT_END':
                if end is not None or len(row)!=4:raise ValueError('duplicate/bad footer')
                end=tuple(map(int,row[1:]))
    if not meta or not end:raise ValueError('snapshot incomplete')
    if meta['version']!=1 or meta['valid']!=1 or meta['page']!=PAGE or meta['total']!=PAGES:raise ValueError('snapshot not valid/supported')
    if not 0x08000000<=meta['heap']<0x14000000 or meta['heap']%0x100000:raise ValueError('bad heap bounds')
    if set(pages)!=set(range(PAGES)):raise ValueError('missing or extra page descriptors')
    blocks={}
    for i,(a,present,digest) in pages.items():
        expected=0x1b1000+i*PAGE if i<STATIC_PAGES else meta['heap']+(i-STATIC_PAGES)*PAGE
        if a!=expected or present not in (0,1):raise ValueError('bad page address/flag')
        if present:
            try:b=b''.join(chunks.pop((i,off)) for off in range(0,PAGE,512))
            except KeyError:raise ValueError('missing page data')
            if fnv(b)!=digest:raise ValueError('page checksum mismatch')
            blocks[a]=b
        elif digest:raise ValueError('unmapped page with nonzero checksum')
    if chunks:raise ValueError('data for unknown/unmapped page')
    if len(blocks)!=meta['present'] or end!=(meta['target'],len(blocks),len(blocks)*PAGE):raise ValueError('snapshot counts/footer mismatch')
    return meta,blocks
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('trace',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    meta,blocks=parse(a.trace);a.out.mkdir(parents=True,exist_ok=True)
    entries=[]
    for address,b in sorted(blocks.items()):
        name=f'{address:08X}.bin';(a.out/name).write_bytes(b)
        entries.append(dict(address=address,file=name,size=len(b),sha256=hashlib.sha256(b).hexdigest()))
    result=dict(metadata=meta,source_sha256=hashlib.sha256(a.trace.read_bytes()).hexdigest(),pages=entries)
    (a.out/'memory.json').write_text(json.dumps(result,indent=2));print(json.dumps(meta))
if __name__=='__main__':main()
