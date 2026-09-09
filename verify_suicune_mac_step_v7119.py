from pathlib import Path
import subprocess,tempfile,sys,shutil,json
r=Path(__file__).resolve().parent
src=r'''
#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
#include "snapshot.h"
static uint64_t clock_ms=4000000000000ULL,clock_tick=1000000000ULL,tick=1000000000ULL;
static uint32_t clock_hz=268111856U,keys,state=0x800032ceU,advance=1149,native_keys=65535;
static uint32_t request[32];static unsigned prepare_fail,read_fail,report_fail,export_fail,export_calls,before_destination,release_count,stage;
static char saved_report[18000];
uint64_t svcGetSystemTick(void){return tick;}
int is_memory_mapped(uint32_t a){return 1;}
uint32_t suicune_native_pre_state(uint32_t*a){*a=advance;return keys?0:state;}
static uint32_t word(uint32_t a){if(a==0x22f644)return 0x8a01000;if(a==0x22f640)return 0x8a01010;if(a==0x22f6d8)return 0x8a02080;if(a==0x22f766)return native_keys;return 0;}
static uint8_t byte(uint32_t a){if(a==0x22f766)return native_keys&255;if(a==0x22f767)return native_keys>>8;return 0;}
static uint64_t wide(uint32_t a){return 1;}
int snapshot7119_request(uint32_t*w){if(read_fail)return 0;memcpy(w,request,128);return 1;}
int snapshot7119_prepare(void){memset(request,0,128);return !prepare_fail;}
int snapshot7119_report(const char*s,uint32_t n){if(report_fail)return 0;assert(n<sizeof(saved_report));memcpy(saved_report,s,n);saved_report[n]=0;return 1;}
void snapshot7119_destination(unsigned b){before_destination=b;}
void host7119_status(unsigned s,unsigned n,unsigned e){stage=s;}
uint32_t gate7118_export(uint32_t*);
#include "runtime.inc"
uint32_t gate7118_export(uint32_t*p){export_calls++;if(export_fail)return 8;Snapshot7116Meta m=mac7119_meta;m.search_id=tick+export_calls;m.advance=advance;m.seed=state&65535;m.clock_tick=tick;mac7119_exported(&m,mac7119_hashes);*p=38;return 0;}
static void reset(void){tick=clock_tick;keys=prepare_fail=read_fail=report_fail=export_fail=export_calls=release_count=stage=0;state=0x800032ceU;advance=1149;native_keys=65535;mac7119_have=mac7119_enabled_flag=mac7119_active=mac7119_inflight=0;mac7119_last_nonce=0;memset(saved_report,0,sizeof(saved_report));Snapshot7116Meta m={.search_id=1234,.advance=advance,.seed=state&65535,.hz=clock_hz,.clock_tick=tick,.clock_ms=clock_ms};uint32_t h[4]={11,22,33,44};mac7119_exported(&m,h);assert(!gate7119_enable());}
static void checksum(void){request[31]=mac7119_checksum(request,124);}
static void make_request(unsigned frames){memset(request,0,128);memcpy(request,"S7119REQ",8);request[2]=1;request[3]=128;request[4]=100;request[6]=(uint32_t)mac7119_meta.search_id;request[7]=mac7119_meta.search_id>>32;request[8]=mac7119_meta.advance;request[9]=mac7119_meta.seed;request[10]=frames;request[11]=30;uint64_t end=tick+600ULL*clock_hz;request[12]=end;request[13]=end>>32;memcpy(request+14,mac7119_hashes,16);checksum();}
static unsigned poll(void){unsigned release=gate7119_poll(keys);if(release){release_count++;advance++;state++;}return release;}
static void finish(void){for(unsigned i=0;i<1000&&gate7119_running();i++){tick+=clock_hz/30;poll();}assert(!gate7119_running());}
int main(int argc,char**argv){
 for(unsigned n=1;n<=32;n++){reset();make_request(n);assert(!poll()&&gate7119_running()&&!release_count);finish();assert(release_count==n&&mac7119_done==n&&!mac7119_error&&export_calls==2);assert(strstr(saved_report,"\"phase\":\"complete\"")&&strstr(saved_report,"\"guest_input_sent\":false"));for(unsigned i=0;i<5;i++){tick+=clock_hz;assert(!poll());}assert(release_count==n);}
 reset();native_keys=0xfcff;make_request(2);assert(!poll());finish();assert(release_count==2&&!mac7119_error);
 reset();make_request(33);assert(mac7119_validate(request,&mac7119_meta,mac7119_hashes,0,tick,0)==2);assert(!poll()&&mac7119_error==22&&!release_count);
 reset();make_request(1);request[18]=1;checksum();assert(mac7119_validate(request,&mac7119_meta,mac7119_hashes,0,tick,0)==2);
 reset();make_request(1);request[14]++;checksum();assert(mac7119_validate(request,&mac7119_meta,mac7119_hashes,0,tick,0)==3);
 reset();make_request(1);assert(mac7119_validate(request,&mac7119_meta,mac7119_hashes,100,tick,0)==4);
 reset();make_request(1);request[12]=tick;request[13]=tick>>32;checksum();assert(mac7119_validate(request,&mac7119_meta,mac7119_hashes,0,tick,0)==5);
 reset();make_request(1);request[31]^=1;assert(!poll()&&!gate7119_running()&&!release_count);
 reset();make_request(1);keys=1;assert(!poll()&&!gate7119_running());keys=0;tick+=clock_hz;assert(!poll()&&gate7119_running());finish();assert(release_count==1);
 reset();make_request(2);assert(!poll());tick+=clock_hz;assert(poll());keys=1;assert(!poll()&&mac7119_done==1);keys=0;finish();assert(release_count==1&&mac7119_error==53&&strstr(saved_report,"aborted"));
 reset();make_request(2);assert(!poll());tick=mac7119_deadline;assert(!poll()&&!gate7119_running()&&!release_count&&mac7119_error==54);
 reset();make_request(2);report_fail=1;assert(!poll()&&!gate7119_running()&&!release_count&&mac7119_error==51);
 reset();make_request(2);export_fail=1;assert(!poll()&&!gate7119_running()&&!release_count&&mac7119_error==48&&before_destination==0);
 reset();make_request(2);native_keys=0;assert(!poll()&&!gate7119_running()&&!release_count&&mac7119_error==27);
 reset();make_request(2);read_fail=1;assert(!poll()&&!gate7119_running());
 reset();prepare_fail=1;assert(gate7119_enable()==10&&!poll());
 reset();make_request(2);assert(!poll());export_fail=1;finish();assert(release_count==2&&mac7119_error==68&&strstr(saved_report,"aborted")&&strstr(saved_report,"\"after_state_id\":\"0000000000000000\""));
 reset();make_request(2);assert(!poll());report_fail=1;finish();assert(release_count==2&&mac7119_error==70);
 reset();make_request(2);request[6]++;checksum();assert(!poll()&&!release_count&&strstr(saved_report,"rejected")&&strstr(saved_report,"\"samples\":[]"));
 reset();make_request(32);assert(!poll());finish();FILE*out=fopen(argv[1],"w");assert(out&&fputs(saved_report,out)>=0&&!fclose(out));
 puts("PASS: exact bounded releases 1..32, one-shot nonce, stale/bad requests, held keys, late deadline, failed journal/export, non-neutral native keys");
}
'''
with tempfile.TemporaryDirectory() as td:
 t=Path(td);(t/'test.c').write_text(src)
 subprocess.run(['cc','-std=c11','-O2','-Wall','-Wno-unused-function','-Wno-unused-variable','-I'+str(r/'v7116'),'-I'+str(r/'v7119_mac'),'-I'+str(r/'3gx/includes'),str(t/'test.c'),'-o',str(t/'test')],check=True)
 subprocess.run([str(t/'test'),str(t/'report.json')],check=True)
 report=json.loads((t/'report.json').read_text());assert len(report['samples'])==33 and report['completed_frames']==32
 assert all(x['release_tick'] for x in report['samples'][:-1]) and not report['samples'][-1]['release_tick']
 for name in ['snapshot.h','read_snapshot.py','test_snapshot.py']:shutil.copyfile(r/'v7116'/name,t/name)
 shutil.copyfile(r/'3gx/sources/v7116_snapshot.c',t/'snapshot.c')
 subprocess.run([sys.executable,'-B',str(t/'test_snapshot.py')],check=True)
s=(r/'3gx/sources/main.c').read_text();assert s.count('if(gate7119_poll(held))break;')==1
block=s[s.index('        if(gate7119_enabled())'):s.index('        if(mac7118_export_pending)')]
assert 'is_paused = false' not in block and 'svcSleepThread' in block
assert 'if(!e)e=gate7119_enable();' in s and 'S7118' not in s and 'S7119 MAC STEP DONE' in s
runtime=(r/'v7119_mac/runtime.inc').read_text();assert 'gate7113_commit' not in runtime and 'writemem' not in runtime and 'shadow7113_run' not in runtime
save=(r/'3gx/sources/v7116_snapshot.c').read_text();assert 'w[30]=7119' in save and '\\"software\\":7119' in save and 'mac_before.bin' in save
print('PASS: generated main routes bounded requests through neutral frame breaks; after/before snapshot tags and paths correct')
