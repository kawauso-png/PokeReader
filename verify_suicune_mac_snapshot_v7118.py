from pathlib import Path
import subprocess,tempfile,sys,shutil
r=Path(__file__).resolve().parent
src=r'''
#include <stdint.h>
#include <assert.h>
#include "snapshot.h"
#define CUR_PROCESS_HANDLE 0xffff8001U
static uint32_t keys,adv=708,state=0x8000bb6b,clock_hz=268111856U;
static uint64_t clock_ms=4000000000000ULL,clock_tick=1000000000ULL;
static unsigned statecalls,saved,mappedfail,clockfail,capturefail,drift,savefail,pidfail;
static uint8_t data[8];
uint32_t get_current_keys(void){return keys;}
uint32_t suicune_native_pre_state(uint32_t*a){*a=adv;return state+((statecalls++&&drift)?1:0);}
int svcGetProcessId(uint32_t*p,uint32_t h){assert(h==CUR_PROCESS_HANDLE);*p=42;return pidfail;}
int is_memory_mapped(uint32_t a){return !mappedfail;}
int clock_capture(void){return !clockfail;}
uint64_t svcGetSystemTick(void){return clock_tick+100;}
uint8_t*suicune_shadow7113_capture(uint32_t a,uint32_t*h){assert(a==adv);*h=0x8a00000;return capturefail?0:data;}
uint32_t word(uint32_t a){assert(a==0x22f6c4);return 0x8800010;}
int snapshot7118_save(const Snapshot7116Meta*m,const uint8_t*c,const uint8_t*d,const uint8_t*rom,uint32_t*h,uint32_t pid){
 assert(pid==42&&m->advance==708&&m->seed==0xbb6b&&m->search_id==clock_tick+100);
 assert(m->launch==m->search_id+600ULL*clock_hz&&((m->resume/4481233ULL)&15U)==14U);
 assert(m->clock_ms==clock_ms&&m->clock_tick==clock_tick&&m->rom_size==0x200000);
 assert(c==(const uint8_t*)0x100000&&d==data&&rom==(const uint8_t*)0x8800010);saved++;return !savefail;
}
#include "export.inc"
static void reset(void){keys=statecalls=saved=mappedfail=clockfail=capturefail=drift=savefail=pidfail=0;state=0x8000bb6b;}
int main(void){uint32_t pid;
 reset();assert(gate7118_export(&pid)==0&&saved==1&&pid==42&&state==0x8000bb6b&&adv==708);
 reset();keys=1;assert(gate7118_export(&pid)==1&&!saved);
 reset();state=0;assert(gate7118_export(&pid)==1&&!saved);
 reset();pidfail=1;assert(gate7118_export(&pid)==2&&!saved);
 reset();mappedfail=1;assert(gate7118_export(&pid)==3&&!saved);
 reset();clockfail=1;assert(gate7118_export(&pid)==4&&!saved);
 reset();capturefail=1;assert(gate7118_export(&pid)==5&&!saved);
 reset();drift=1;assert(gate7118_export(&pid)==7&&!saved);
 reset();savefail=1;assert(gate7118_export(&pid)==8&&saved==1);
 return 0;}
'''
with tempfile.TemporaryDirectory() as td:
 t=Path(td);(t/'test.c').write_text(src)
 subprocess.run(['cc','-std=c11','-O2','-I'+str(r/'v7116'),'-I'+str(r/'v7118_mac'),str(t/'test.c'),'-o',str(t/'test')],check=True)
 subprocess.run([str(t/'test')],check=True)
 # Exercise the actual new serialized payload through the existing integrity suite.
 for name in ['snapshot.h','read_snapshot.py','test_snapshot.py']:shutil.copyfile(r/'v7116'/name,t/name)
 shutil.copyfile(r/'3gx/sources/v7116_snapshot.c',t/'snapshot.c')
 subprocess.run([sys.executable,'-B',str(t/'test_snapshot.py')],check=True)
s=(r/'3gx/sources/main.c').read_text();assert s.count('gate7118_export(&pid)')==1
assert 'if(mac7118_export_pending)' in s and 'if(held){svcSleepThread(1000000);continue;}' in s
assert 'S7118 MAC SNAPSHOT READY' in s and 'S7117' not in s
assert 'mac7118_export_pending=true;' in s and 'NO GAME INPUT SENT' in s
assert 'suicune_exact2_release_confirmed();' in s and 'suicune_neutral_probe_remaining--;' in s
export=(r/'v7118_mac/export.inc').read_text()
assert 'shadow7113_run(' not in export and 'gate7113_commit(' not in export
save=(r/'v7118_mac/save.inc').read_text();assert save.index('FSFILE_SetSize(mw.file,0)')<save.index('snapshot7116_emit')<save.index('sd_put(&mw')
print('PASS: snapshot-only capture; held keys, missing mapping/clock/capture, changed PRE and SD failure rejected; no plan armed')
