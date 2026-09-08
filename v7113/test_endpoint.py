"""Actual private replay must wait for both ROM-qualified enemy DV stores."""
from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parent
src=r'''
#include "shadow.h"
#include "dv_endpoint.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
static uint64_t rtc(unsigned f,void*p){return 0;}
static void put(uint8_t*p,unsigned off,uint32_t v){memcpy(p+off,&v,4);}
static uint32_t ldr(unsigned i,unsigned rd,unsigned lit){return 0xe59f0000|(rd<<12)|(lit*4-i*4-8);}
int main(void){
 DvEndpoint7115 e={0};unsigned b=0x8001000;
 dv7115_observe(&e,b,b+0x23e,1,0xaa,0x69bd,15,1);assert(!e.mask);
 dv7115_observe(&e,b,b+0x23d,1,0x6a,0x69bc,14,1);assert(!e.mask);
 dv7115_observe(&e,b,b+0x23d,1,0x6a,0x69bb,15,1);assert(!e.mask);
 dv7115_observe(&e,b,b+0x23d,2,0xaa6a,0x69bc,15,1);assert(!e.mask);
 dv7115_observe(&e,b,b+0x23d,1,0x6a,0x69bc,15,2);assert(e.mask==1);
 dv7115_observe(&e,b+4096,b+4096+0x23e,1,0xaa,0x69bd,15,2);assert(e.mask==1);
 dv7115_observe(&e,b,b+0x23e,1,0xaa,0x69bd,15,3);assert(e.mask==3&&e.dv==0x6aaa&&e.frame==3);
 Shadow7113Input in={0};in.static_data=calloc(0x14f000,1);in.heap_data=calloc(0x100000,1);
 uint8_t*code=calloc(0xb1000,1);in.code=code;in.heap_base=0x8000000;in.rtc=rtc;
 put(in.static_data,0x22f768-0x1b1000,b);put(in.static_data,0x22f6d8-0x1b1000,in.heap_base+0x8080);
 in.heap_data[0x809d]=15;put(code,0x1a857c-0x100000,0x22f640);
 uint32_t prog[]={0,0,0xe5812000,0,0xe3a0002a,0xe5c30000,0xe2822001,0xe5812000,0xe3a000aa,0xe5c30001,0xe12fff1e,0x22f5fc,0x69bc,0x800123d};
 prog[0]=ldr(0,1,11);prog[1]=ldr(1,2,12);prog[3]=ldr(3,3,13);
 memcpy(code+0xa824c,prog,sizeof(prog));
 Shadow7113Result out=shadow7113_run(&in,1100);
 assert(!out.error&&out.shiny&&out.dv==0x2aaa&&out.dv_write_mask==3&&out.frame==0&&out.final==0);
 /* Pre-existing shiny bytes without the expected stores must never select. */
 put(code,0xa824c,0xe12fff1e);out=shadow7113_run(&in,1100);
 assert(out.error==110&&!out.shiny&&!out.dv_write_mask&&!out.dv);
 memcpy(code+0xa824c,prog,sizeof(prog));put(code,0xa824c+9*4,0xe1a00000);
 out=shadow7113_run(&in,1100);assert(out.error==110&&out.dv_write_mask==1&&!out.shiny);
 memcpy(code+0xa824c,prog,sizeof(prog));in.heap_data[0x809d]=14;
 out=shadow7113_run(&in,1100);assert(out.error==110&&!out.dv_write_mask&&!out.shiny);
 free(code);free(in.static_data);free(in.heap_data);
}
'''
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'test.c').write_text(src)
 subprocess.run(['cc','-O2','-fno-strict-aliasing','-I'+str(r),str(d/'test.c'),str(r/'shadow.c'),'-o',str(d/'test')],check=True)
 subprocess.run([str(d/'test')],check=True)
print('PASS: actual replay stops on complete qualified DV stores; stale values, low-only, partial, wrong-PC/bank and cross-bank stores cannot select')
