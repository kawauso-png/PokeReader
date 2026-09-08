"""Stamp the replay that waits for actual enemy-DV writes."""
from pathlib import Path
r=Path(__file__).resolve().parent
for name in ['3gx/sources/main.c','reader_core/src/crystal/trace.rs']:
 p=r/name;s=p.read_text();assert 'S7114' in s
 s=s.replace('S7114','S7115').replace('STALLPHASE,V7114,','STALLPHASE,V7115,');p.write_text(s)
print('Applied v7115: actual enemy-DV write endpoint; existing physical input and M14 schedule retained')
