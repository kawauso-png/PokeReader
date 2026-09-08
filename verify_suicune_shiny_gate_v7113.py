from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parent
s=(r/'3gx/sources/main.c').read_text()
assert 'clock7110_collection=false' in s
for name in ['arm_core.c','shadow.c','gate_runtime.c']:
 assert (r/'v7113'/name).read_bytes()==(r/'3gx/sources'/('v7113_'+name)).read_bytes()
assert 'suicune_shadow7113_capture' in (r/'reader_core/src/crystal/snapshot7111.rs').read_text()
assert 'hid_up_mask_begin(' not in (r/'v7113/gate_runtime.c').read_text()
assert 'shadow7113_run(&in,1100)' in (r/'v7113/gate_runtime.c').read_text()
start=s.index('            if (gate7113_active()) {\n                u64 now=')
end=s.index('        // Y+L schedules',start)
block=s[start:end].rstrip();assert block.endswith('}');block=block[:-1]
head=r'''#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <assert.h>
typedef uint32_t u32;typedef uint64_t u64;
enum{KEY_A=1,KEY_B=2,KEY_X=4,KEY_Y=8,KEY_DUP=16,KEY_DDOWN=32,KEY_DLEFT=64,KEY_DRIGHT=128,KEY_L=256,KEY_R=512,KEY_START=1024,KEY_SELECT=2048};
static u32 held,just_pressed,gate7113_last_seconds=~0U,fixed_frames_remaining;static u64 tick,target=10000000;
static bool active=true,suicune_live_pass_ready=true,suicune_wait_up_after_b=true,fixed_run_pending,fixed_armed=true,suicune_auto_resume_pending,suicune_phase_lock_active,is_paused=true,rank7108_hunting=true;
static int ok=1,calls=0;
u32 suicune_rtc7112_launch(void){calls++;return ok;}
void svcSleepThread(int x){}void v7102_panel(const char*a,const char*b,const char*c){}
u64 svcGetSystemTick(void){return tick;}int gate7113_active(void){return active;}u64 gate7113_launch_tick(void){return target;}u32 gate7113_dv(void){return 0x2aaa;}void gate7113_cancel(void){active=false;}
void attempt(void){for(int n=0;n<1;n++){BLOCK}}
int main(void){
 held=KEY_DUP;tick=target-1;attempt();assert(is_paused&&!calls);
 tick=target;held=KEY_B|KEY_DUP;attempt();assert(is_paused&&!calls);
 held=KEY_DUP;ok=0;attempt();assert(is_paused&&calls==1);
 ok=1;attempt();assert(!is_paused&&calls==2&&!suicune_wait_up_after_b);
 is_paused=true;suicune_live_pass_ready=true;suicune_wait_up_after_b=true;tick=target+2681119;attempt();assert(is_paused&&!active&&!suicune_live_pass_ready&&calls==2);
 active=true;suicune_live_pass_ready=true;suicune_wait_up_after_b=true;tick=target-1;just_pressed=KEY_SELECT;held=KEY_SELECT;attempt();assert(is_paused&&!active&&calls==2);
}
'''.replace('BLOCK',block)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'flow.c').write_text(head);subprocess.run(['cc','-std=c99',str(d/'flow.c'),'-o',str(d/'flow')],check=True);subprocess.run([str(d/'flow')],check=True)
# Test reserved M14 ordering: no release confirmation until after timeout and
# last physical-key validation. No input byte is written in this path.
a=s.index('        if (suicune_exact2_release_waiting())');b=s.index('        if (suicune_release_resume_pending)',a);release=s[a:b]
assert release.index('if(now>=target)')<release.index('suicune_exact2_release_confirmed()')
assert release.index('if(get_current_keys()!=0)')<release.index('suicune_exact2_release_confirmed()')<release.index('is_paused = false')
assert 'const u32 wanted = 14U' in release and 'target=gate7113_resume_tick()' in release
assert 'write' not in release
# Small C instruction/clock tests are portable to CI without ROM or Unicorn.
test=r'''#include "shadow.h"
#include <assert.h>
#include <stdint.h>
static uint32_t op;static uint32_t read(uint32_t a,unsigned n){assert(a==0x1000&&n==4);return op;}static void write(uint32_t a,uint32_t v,unsigned n){assert(0);}
int main(void){Arm7113 c={0};c.r[15]=0x1000;c.r[0]=0xffffffff;op=0xe2900001;arm7113_step(&c,read,write);assert(!c.error&&c.r[0]==0&&(c.flags&0xf0000000)==0x60000000);c.r[15]=0x1000;c.r[1]=0x80000000;op=0xe0d10000;arm7113_step(&c,read,write);assert(!c.error&&c.r[0]==0x80000000);assert(shadow7113_pack_ms(3997987199500ULL)+0x0c5ULL==shadow7113_pack_ms(3997987200500ULL));}
'''
# Date rollover validated explicitly with numeric components, no host timezone.
test=test.replace('assert(shadow7113_pack_ms(3997987199500ULL)+0x0c5ULL==shadow7113_pack_ms(3997987200500ULL));','assert(shadow7113_pack_ms(0)==((uint64_t)1900<<26|1ULL<<22|1ULL<<17));assert(shadow7113_pack_ms(86400000)==((uint64_t)1900<<26|1ULL<<22|2ULL<<17));')
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'unit.c').write_text(test);subprocess.run(['cc','-std=c99','-I'+str(r/'v7113'),str(d/'unit.c'),str(r/'v7113/arm_core.c'),str(r/'v7113/shadow.c'),'-o',str(d/'unit')],check=True);subprocess.run([str(d/'unit')],check=True)
subprocess.run(['python3','-B',str(r/'v7113/test_gate_runtime.py')],check=True)
print('PASS: native candidate gate integration, physical-UP schedule/cancel/expiry/failure, M14 key checks, ARM flags and epoch conversion')
