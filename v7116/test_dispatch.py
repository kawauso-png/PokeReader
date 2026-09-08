"""Differentially exercise accelerated blocks against the generic instruction loop."""
from pathlib import Path
import csv,subprocess,tempfile
R=Path(__file__).resolve().parent
ops=[(int(r['pc'],16),int(r['op'],16)) for r in csv.DictReader((R/'hot_ops.csv').open())]
src=r'''
#include "shadow.c"
#include <assert.h>
#include <stdio.h>
static unsigned rng=19;
static unsigned rand32(void){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
static void clear_extra(void){for(unsigned j=0;j<nextra;j++){free(extra[j].data);free(extra[j].known);}nextra=0;}
static unsigned eh(void){unsigned h=2166136261U;for(unsigned j=0;j<nextra;j++){h=(h^extra[j].base)*16777619U;for(unsigned k=0;k<4096;k++){h=(h^extra[j].data[k])*16777619U;h=(h^extra[j].known[k])*16777619U;}}return h;}
static unsigned ops[][2]={ OPS };
int main(void){
 Shadow7113Input input={0};input.static_data=calloc(0x14f000,1);input.heap_data=calloc(0x100000,1);input.heap_base=0x8000000;input.rom_base=0x9000000;input.rom_size=0x200000;input.rom=calloc(0x200000,1);uint8_t*code=calloc(0xb1000,1);input.code=code;in=&input;io=input.heap_base+0x8000;dv_bank=input.heap_base+0x1000;
 for(unsigned j=0;j<sizeof(ops)/sizeof(ops[0]);j++)memcpy(code+ops[j][0]-0x100000,&ops[j][1],4);
 assert(code_guard());code[ops[0][0]-0x100000]^=1;assert(!code_guard());code[ops[0][0]-0x100000]^=1;
 uint8_t*out=malloc(0x25f000);unsigned count=0;
 for(unsigned j=0;j<sizeof(ops)/sizeof(ops[0]);j++)for(unsigned trial=0;trial<2;trial++){
  memset(input.static_data,0,0x14f000);memset(input.heap_data,0,0x100000);memset(stack,0,sizeof(stack));memset(&endpoint,0,sizeof(endpoint));clear_extra();fail=0;
  Arm7113 initial={0};for(unsigned k=0;k<16;k++){unsigned v=rand32();initial.r[k]=(v&3)==0?v:(v&3)==1?0x22f600+(v&1020):(v&3)==2?0x8000000+(v&4092):0x700e000+(v&4092);}initial.r[13]=0x700f000;initial.r[4]=0x22f5f8;initial.r[15]=ops[j][0];initial.flags=rand32()&0xf0000000;
  cpu=initial;assert(fast_step());Arm7113 accelerated=cpu;unsigned f=fail,extra_hash=eh(),pages=nextra;
  memcpy(out,input.static_data,0x14f000);memcpy(out+0x14f000,input.heap_data,0x100000);memcpy(out+0x24f000,stack,sizeof(stack));
  memset(input.static_data,0,0x14f000);memset(input.heap_data,0,0x100000);memset(stack,0,sizeof(stack));memset(&endpoint,0,sizeof(endpoint));clear_extra();fail=0;cpu=initial;
  for(uint64_t n=0;n<accelerated.steps;n++){assert(!cpu.error&&!fail);shadow_arm_inline(&cpu,readmem,writemem);}
  if(memcmp(&cpu,&accelerated,sizeof(cpu))||fail!=f||pages!=nextra||eh()!=extra_hash||memcmp(out,input.static_data,0x14f000)||memcmp(out+0x14f000,input.heap_data,0x100000)||memcmp(out+0x24f000,stack,sizeof(stack))){fprintf(stderr,"block mismatch %X trial%u steps%llu\\n",ops[j][0],trial,(unsigned long long)accelerated.steps);return 1;}count++;
 }
 clear_extra();printf("PASS: %u block/register/flags/memory/error comparisons; changed code disables specialization\\n",count);return 0;
}
'''.replace(' OPS ',','.join('{0x%x,0x%x}'%p for p in ops))
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.c').write_text(src)
 subprocess.run(['cc','-O3','-fno-strict-aliasing','-I'+str(R),'-I'+str(R.parent/'v7113'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
