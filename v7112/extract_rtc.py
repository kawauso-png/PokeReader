"""Strict input-only RTC launch reference reader (no observed DV/clock inputs)."""
from pathlib import Path
import csv,io

def fnv(b):
 h=2166136261
 for v in b:h=((h^v)*16777619)&0xffffffff
 return h

def parse(path):
 raw=Path(path).read_bytes()
 if any(not l.startswith(b'BUCKET738,') for l in raw.splitlines() if b'\0' in l):raise ValueError('NUL outside legacy BUCKET738')
 stages={};parts={};ends={}
 for r in csv.reader(io.StringIO(raw.replace(b'\0',b'').decode())):
  if not r:continue
  if r[0]=='R7112_RTC':
   if len(r)!=10 or r[1]!='1':raise ValueError('invalid RTC header')
   stage=int(r[2])
   if stage not in (0,1) or stage in stages:raise ValueError('duplicate/unknown RTC stage')
   d=dict(target=int(r[3]),valid=int(r[4]),begin=int(r[5]),end=int(r[6]),base=int(r[7],16),size=int(r[8]),fnv=int(r[9],16))
   if d['valid']!=1 or d['begin']>d['end'] or d['base']!=0x1ff81000 or d['size']!=4096:raise ValueError('invalid RTC capture')
   stages[stage]=d
  elif r[0]=='R7112_RTC_DATA':
   if len(r)!=4:raise ValueError('RTC chunk format')
   key=(int(r[1]),int(r[2]));b=bytes.fromhex(r[3])
   if key in parts or key[1] not in range(0,4096,512) or len(b)!=512:raise ValueError('bad RTC chunk')
   parts[key]=b
  elif r[0]=='R7112_RTC_END':
   if len(r)!=3 or int(r[1]) in ends:raise ValueError('duplicate RTC footer')
   ends[int(r[1])]=int(r[2])
 if set(stages)!={0,1} or set(ends)!={0,1}:raise ValueError('PRE and launch RTC required')
 if stages[0]['target']!=stages[1]['target']:raise ValueError('RTC target mismatch')
 for stage,d in stages.items():
  try:b=b''.join(parts.pop((stage,off)) for off in range(0,4096,512))
  except KeyError:raise ValueError('missing RTC data')
  if fnv(b)!=d['fnv'] or ends[stage]!=d['target']:raise ValueError('RTC checksum/footer mismatch')
  d['bytes']=b
 if parts:raise ValueError('extra RTC chunks')
 if stages[0]['end']>stages[1]['begin']:raise ValueError('RTC stage order')
 return stages
