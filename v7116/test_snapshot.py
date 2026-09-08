from pathlib import Path
import tempfile,subprocess,sys,struct
sys.path.insert(0,str(Path(__file__).resolve().parent))
from read_snapshot import read,fnv
R=Path(__file__).resolve().parent
src=r'''
#include "snapshot.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
static FILE*f;static unsigned calls,limit=100;
static int put(void*x,const void*b,uint32_t n){if(++calls>limit)return 0;return fwrite(b,n,1,f)==1;}
int main(int ac,char**av){unsigned char*c=malloc(0xb1000),*d=malloc(0x24f000),*r=malloc(0x200000);for(unsigned i=0;i<0xb1000;i++)c[i]=i*17;for(unsigned i=0;i<0x24f000;i++)d[i]=i*7+1;for(unsigned i=0;i<0x200000;i++)r[i]=i*3+2;
Snapshot7116Meta m={.search_id=0x12345678abcdef01ULL,.clock_ms=4000123456789ULL,.clock_tick=0x100012345ULL,.launch=0x200012345ULL,.resume=0x300012345ULL,.check=7,.advance=8192,.seed=0xabcd,.rom_base=0x9000000,.rom_size=0x200000,.heap_base=0x8000000,.hz=268111856};unsigned hashes[4];
f=fopen(av[1],"wb");assert(f&&snapshot7116_emit(&m,c,d,r,put,0,hashes));assert(!fclose(f));
for(unsigned i=0;i<4;i++){calls=0;limit=i;f=tmpfile();assert(!snapshot7116_emit(&m,c,d,r,put,0,hashes));fclose(f);}free(c);free(d);free(r);return 0;}
'''
with tempfile.TemporaryDirectory() as td:
 t=Path(td);(t/'test.c').write_text(src);subprocess.run(['cc','-O2','-I'+str(R),str(t/'test.c'),str(R/'snapshot.c'),'-o',str(t/'test')],check=True);subprocess.run([str(t/'test'),str(t/'valid.bin')],check=True)
 m,blocks=read(t/'valid.bin');assert m['search_id']=='12345678ABCDEF01' and m['check']==7 and m['advance']==8192 and m['seed']=='ABCD'
 assert m['clock_ms']==4000123456789 and m['clock_tick']==0x100012345 and m['launch']==0x200012345 and m['resume']==0x300012345
 assert [a for a,b in blocks]==[0x100000,0x1b1000,0x8000000] and blocks[1][1][4097]==(4097*7+1)&255
 good=(t/'valid.bin').read_bytes();bad=[]
 for pos in [0,40,124,128,128+0xb1000,128+0x200000,len(good)-1]:
  b=bytearray(good);b[pos]^=1;bad.append(b)
 bad.extend([good[:-1],good+b'0'])
 for b in bad:
  (t/'bad.bin').write_bytes(b)
  try:read(t/'bad.bin')
  except ValueError:pass
  else:raise AssertionError('Corrupt/truncated snapshot accepted')
print('PASS: snapshot round trip, identity/timing, callback failures and damaged/incomplete inputs')
