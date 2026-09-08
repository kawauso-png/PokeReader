"""Validate a local predictor input; ROM bytes are supplied locally, never exported."""
from pathlib import Path
import struct,json,argparse

def fnv(b):
 h=2166136261
 for v in b:h=((h^v)*16777619)&0xffffffff
 return h

def read(path):
 b=Path(path).read_bytes()
 if len(b)<136 or b[:8]!=b'S7116PRE':raise ValueError('Invalid snapshot header')
 w=struct.unpack_from('<32I',b)
 if w[2:4]!=(1,128) or fnv(b[:124])!=w[31]:raise ValueError('Header version/hash mismatch')
 if w[25:30]!=(0xb1000,0x14f000,0x100000,0x1b1000,0x100000):raise ValueError('Unexpected memory layout')
 if len(b)!=128+sum(w[25:28])+8 or b[-8:]!=b'DONE7116':raise ValueError('Incomplete snapshot')
 blocks=[];off=128
 for a,n,h in zip([w[29],w[28],w[11]],w[25:28],w[21:24]):
  p=b[off:off+n];off+=n
  if fnv(p)!=h:raise ValueError('Payload hash mismatch')
  blocks.append((a,p))
 if not 0x8000000<=w[11]<0x14000000 or w[11]&0xfffff or w[10]!=0x200000 or w[12]!=268111856:raise ValueError('Unexpected native layout/clock')
 wide=lambda i:w[i]|w[i+1]<<32
 m=dict(version='S7116',search_id=f'{wide(4):016X}',check=w[6],advance=w[7],seed=f'{w[8]:04X}',rom_base=w[9],rom_size=w[10],heap_base=w[11],hz=w[12],clock_ms=wide(13),clock_tick=wide(15),launch=wide(17),resume=wide(19),hashes=list(w[21:25]))
 return m,blocks

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('snapshot');p.add_argument('--rom');p.add_argument('--output');a=p.parse_args();meta,blocks=read(a.snapshot)
 if a.output:
  if not a.rom:p.error('--output requires the already captured local --rom')
  rom=Path(a.rom).read_bytes()
  if len(rom)!=meta['rom_size'] or fnv(rom)!=meta['hashes'][3]:raise ValueError('ROM does not match this input')
  with Path(a.output).open('wb') as out:
   for addr,data in blocks+[(meta['rom_base'],rom)]:out.write(struct.pack('<II',addr,len(data)));out.write(data)
 print(json.dumps(meta,indent=2))
