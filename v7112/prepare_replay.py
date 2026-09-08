"""Export only ROM + frozen PRE + launch RTC inputs for native replay."""
from pathlib import Path
import argparse,csv,io,json,hashlib,struct,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'v7111'))
from extract_snapshot import parse as snapshot
from extract_rtc import parse as rtc
ROM_SHA='68ef4286568a27fd9b1e9b26ea2ad703afac127dab06cf46ff5afbd51f5a4ecb'
TAGS={'NATIVE_CODE':0xb1000,'PRE_EMU':0x480,'PRE_CPU':64,'PRE_RAM':8192,'PRE_IO_BACKING':256}
def export(trace,rom,out,allow_missing_rtc=False):
 meta,pages=snapshot(trace);raw=trace.read_bytes();parts={k:{} for k in TAGS}
 # The snapshot validator already rejects NUL outside the known legacy field.
 for r in csv.reader(io.StringIO(raw.replace(b'\0',b'').decode())):
  if len(r)>1 and r[0]=='R7102_BLOB' and r[1] in TAGS:
   if len(r)!=5:raise ValueError('bad input blob row')
   tag=r[1];off=int(r[3]);b=bytes.fromhex(r[4])
   if off in parts[tag]:raise ValueError('duplicate input blob')
   parts[tag][off]=b
 blobs={}
 for tag,chunks in parts.items():
  b=bytearray()
  for off,chunk in sorted(chunks.items()):
   if off!=len(b):raise ValueError('missing input blob chunk')
   b.extend(chunk)
  if len(b)!=TAGS[tag]:raise ValueError('wrong input blob size')
  blobs[tag]=bytes(b)
 def word(a):return int.from_bytes(blobs['PRE_EMU'][a-0x22f5e0:a-0x22f5e0+4],'little')
 if blobs['PRE_CPU']!=blobs['PRE_EMU'][:64]:raise ValueError('CPU/EMU conflict')
 for addr,b in [(0x22f5e0,blobs['PRE_EMU']),(word(0x22f6c8),blobs['PRE_RAM']),(word(0x22f6d8)-128,blobs['PRE_IO_BACKING'])]:
  for i,v in enumerate(b):
   a=addr+i
   if a&~4095 not in pages or pages[a&~4095][a&4095]!=v:raise ValueError('conflicting/missing frozen view')
 rb=rom.read_bytes()
 if hashlib.sha256(rb).hexdigest()!=ROM_SHA:raise ValueError('unverified VC ROM; dump/verify first')
 blocks={0x100000:blobs['NATIVE_CODE'],word(0x22f6c4):rb,**pages}
 # ROM's trailing page overlaps the heap capture by 16 bytes; require equality.
 rombase=word(0x22f6c4)
 for a,b in pages.items():
  lo=max(a,rombase);hi=min(a+len(b),rombase+len(rb))
  if lo<hi and b[lo-a:hi-a]!=rb[lo-rombase:hi-rombase]:raise ValueError('ROM/snapshot overlap mismatch')
 out.mkdir(parents=True,exist_ok=True)
 memory=out/'pre_memory.bin'
 with memory.open('wb') as f:
  for addr,b in sorted(blocks.items()):f.write(struct.pack('<II',addr,len(b))+b)
 manifest=dict(scope='Input only; no observed DIV clocks, final DV, END blobs, or later FRAME samples used',target=meta['target'],trace_sha256=hashlib.sha256(raw).hexdigest(),rom_sha256=ROM_SHA,memory_sha256=hashlib.sha256(memory.read_bytes()).hexdigest(),snapshot_pages=len(pages),rtc_source=None)
 if not allow_missing_rtc or b'R7112_RTC,' in raw:
  stages=rtc(trace)
  if stages[1]['target']!=meta['target']:raise ValueError('launch/snapshot target mismatch')
  launch=stages[1];(out/'launch_rtc.bin').write_bytes(struct.pack('<QQ',launch['begin'],launch['end'])+launch['bytes'])
  manifest['rtc_source']='R7112_RTC stage 1 (physical UP before any guest execution)'
 else:manifest['rtc_source']='Missing; retrospective manually supplied launch time only. Not a prospective prediction.'
 (out/'inputs.json').write_text(json.dumps(manifest,indent=2));return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trace',type=Path,required=True);p.add_argument('--rom',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-missing-rtc',action='store_true');a=p.parse_args()
 print(json.dumps(export(a.trace,a.rom,a.out,a.allow_missing_rtc),indent=2))
