"""Generate constant-opcode blocks from a reviewed instruction template list.

No ROM, RAM, or PRE snapshot is read or emitted. The runtime verifies every
selected instruction before enabling blocks, and otherwise uses the generic
interpreter. Special observer/RTC/LCD/serial hook entries always leave blocks.
"""
from pathlib import Path
import csv,argparse
R=Path(__file__).resolve().parent

def generate():
 pairs=[(int(r['pc'],16),int(r['op'],16)) for r in csv.DictReader((R/'hot_ops.csv').open())]
 assert pairs==sorted(pairs) and len({a for a,b in pairs})==len(pairs)
 hooks={0x178abc,0x1a7584,0x19cd10,0x14aa9c,0x1af11c}
 assert all(0x100000<=a<0x1b1000 and a%4==0 and a not in hooks for a,b in pairs)
 core=(R.parent/'v7113/arm_core.c').read_text().replace('arm7113_step(Arm7113*a,ArmRead read,ArmWrite write)','arm7113_const(Arm7113*a,ArmRead read,ArmWrite write,uint32_t pc,uint32_t op)').replace('uint32_t pc=a->r[15],op=read(pc,4),next=pc+4;','uint32_t next=pc+4;')
 core=core[core.index('ARM7113_API void'):].replace('ARM7113_API void','static inline __attribute__((always_inline)) void')
 out=['/* Generated instruction templates. Code guard required; unknown code uses the generic interpreter. */','#include "const_core.h"','static int fast_step(void){','uint64_t limit=cpu.steps+256;','dispatch: if(cpu.error||fail||cpu.steps>=limit)return 1;','switch(cpu.r[15]){']
 out += [f'case 0x{a:x}:goto L{a:x};' for a,b in pairs]
 out += ['default:return cpu.steps+256!=limit;}']
 for j,(a,op) in enumerate(pairs):
  out += [f'L{a:x}: arm7113_const(&cpu,readmem,writemem,0x{a:x},0x{op:08x});']
  if j+1<len(pairs) and pairs[j+1][0]==a+4 and j%16!=15:out += [f'if(cpu.r[15]!=0x{a+4:x}||cpu.error||fail)goto dispatch;']
  else:out += ['goto dispatch;']
 out += ['}']
 dispatch='\n'.join(out)
 guard='static int code_guard(void){fast_mismatch=0;\n'+''.join(f'if(readmem(0x{a:x},4)!=0x{op:08x}U){{fast_mismatch=0x{a:x};return 0;}}\n' for a,op in pairs)+'return 1;}\n'
 shadow=(R.parent/'v7113/shadow.c').read_text().replace('static int hook(void)',guard+'#include "fast_dispatch.h"\nstatic int hook(void)')
 shadow=shadow.replace('static uint32_t io,dv_bank;', 'static uint32_t fast_mismatch,io,dv_bank;')
 shadow=shadow.replace('io=readmem(0x22f6d8,4)-128;dv_bank=readmem(0x22f768,4);','io=readmem(0x22f6d8,4)-128;dv_bank=readmem(0x22f768,4);int fast_enabled=code_guard();uint64_t accelerated_steps=0;unsigned accelerated_blocks=0;')
 shadow=shadow.replace('if(!hook())shadow_arm_inline(&cpu,readmem,writemem);if(++local>10000000)','uint64_t before=cpu.steps;if(!hook()){if(fast_enabled&&fast_step()){accelerated_blocks++;accelerated_steps+=cpu.steps-before;}else shadow_arm_inline(&cpu,readmem,writemem);}uint64_t took=cpu.steps-before;local+=(unsigned)(took?took:1);if(local>10000000)')
 shadow=shadow.replace('r.dv_write_mask=endpoint.mask;', 'r.fast_enabled=fast_enabled;r.fast_steps=accelerated_steps;r.fast_blocks=accelerated_blocks;r.fast_mismatch=fast_mismatch;r.dv_write_mask=endpoint.mask;')
 return {'const_core.h':core,'fast_dispatch.h':dispatch,'shadow.c':shadow}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
 for name,text in generate().items():
  if a.check:assert (R/name).read_text()==text,name
  else:(R/name).write_text(text)
 print('PASS: guarded instruction templates reproduced' if a.check else 'Generated guarded instruction blocks')
