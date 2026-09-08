from pathlib import Path
import tempfile,subprocess,sys,os,json
r=Path(__file__).resolve().parent;sys.path.insert(0,str(r/'v7112'))
from extract_rtc import parse
c=(r/'3gx/sources/main.c').read_text();research=(r/'reader_core/src/crystal/research.rs').read_text()
assert c.count('if (!suicune_rtc7112_launch())')==1
launch=c.index('if (!suicune_rtc7112_launch())');resume=c.index('is_paused = false;',launch);assert launch<resume
assert 'S7112 RTC RECORD READY' in c
assert 'rtc7112::arm(target,PRE_OK && MODE==3)' in research
assert 'rtc7112::save();' in research
source=(r/'v7112/rtc.rs').read_text();assert source==(r/'reader_core/src/crystal/rtc7112.rs').read_text()
hot=source[:source.index('pub fn save()')]
for token in ('trace_file_write','write_volatile','request_resume','request_pause','gb_mem::write','String::'):assert token not in hot
for name in ('clock7110.rs','hook.rs'):assert 'rtc7112' not in (r/'reader_core/src/crystal'/name).read_text()
assert (r/'reader_core/src/crystal/clock7110.rs').read_bytes()==(r/'v7110/clock.rs').read_bytes()
with tempfile.TemporaryDirectory() as td:
 d=Path(td);test=(r/'v7112/test_rtc.rs.in').read_text().replace('RTC_PATH',json.dumps(str(r/'v7112/rtc.rs')))
 (d/'test.rs').write_text(test);subprocess.run(['rustc','--edition=2021','--test',str(d/'test.rs'),'-o',str(d/'test')],check=True)
 subprocess.run([str(d/'test'),'--test-threads=1'],check=True,env={**os.environ,'RTC_TEST_OUT':str(d/'rtc.csv')})
 good=d/'rtc.csv';stages=parse(good);assert set(stages)=={0,1} and stages[1]['target']==3213
 data=good.read_text()
 for name,bad in [('truncate',data.rsplit('R7112_RTC_END',1)[0]),('duplicate',data+data),('corrupt',data.replace('04050607','04050608',1)),('invalid',data.replace(',3213,1,',',3213,0,',1)),('NUL',data+'BAD,\0\n')]:
  f=d/(name+'.csv');f.write_text(bad)
  try:parse(f)
  except ValueError:pass
  else:raise AssertionError(name)
# Execute the actual physical-UP branch including the new failure guard.
start=c.index('            // Neutral delay is complete.')
end=c.index('        // Y+L schedules',start)
block=c[start:end].rstrip()
# Drop the closing brace of the surrounding suicune_wait_up_after_b branch.
assert block.endswith('}')
block=block[:-1]
harness=r'''#include <stdint.h>
#include <stdbool.h>
#include <assert.h>
typedef uint32_t u32;
enum {KEY_A=1,KEY_B=2,KEY_X=4,KEY_Y=8,KEY_DUP=16,KEY_DDOWN=32,KEY_DLEFT=64,KEY_DRIGHT=128,KEY_L=256,KEY_R=512,KEY_START=1024,KEY_SELECT=2048};
static u32 held,fixed_frames_remaining;static bool suicune_live_pass_ready=true,suicune_wait_up_after_b=true,fixed_run_pending,fixed_armed,suicune_auto_resume_pending,suicune_phase_lock_active,is_paused=true;
static int ok=1,calls=0;
u32 suicune_rtc7112_launch(void){calls++;return ok;}
void svcSleepThread(int x){}void v7102_panel(const char*a,const char*b,const char*c){}
void tick(void){for(int n=0;n<1;n++){BLOCK}}
int main(void){held=KEY_DUP|KEY_B;tick();assert(!calls&&is_paused);held=KEY_DUP;suicune_live_pass_ready=false;tick();assert(!calls&&is_paused);suicune_live_pass_ready=true;ok=0;tick();assert(calls==1&&is_paused&&suicune_wait_up_after_b);ok=1;tick();assert(calls==2&&!is_paused&&!suicune_wait_up_after_b);}
'''.replace('BLOCK',block)
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'flow.c').write_text(harness);subprocess.run(['cc','-std=c99',str(d/'flow.c'),'-o',str(d/'flow')],check=True);subprocess.run([str(d/'flow')],check=True)
print('PASS: RTC capture retries/bounds, missing mapping, once-only launch, parser integrity, pre-resume placement, no guest writes')
