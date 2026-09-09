
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
static uint32_t seed,selected,models,committed,error;
static uint64_t launch,resume,export_delay;
static unsigned log_fail,arm_fail,hash_change,arm_calls;
int snapshot7120_samples(const void*data,uint32_t n){assert(n>=56&&n<=56*65536);return !log_fail;}
int host7120_arm(void){arm_calls++;return !arm_fail;}
void gate7113_cancel(void){selected=models=committed=0;launch=resume=0;}
uint32_t gate7118_export(uint32_t*);
#include "runtime.inc"
uint32_t gate7118_export(uint32_t*p){export_calls++;tick+=export_delay;if(hash_change)mac7119_hashes[1]++;if(export_fail)return 8;Snapshot7116Meta m=mac7119_meta;m.search_id=tick+export_calls;m.advance=advance;m.seed=state&65535;m.clock_tick=tick;mac7119_exported(&m,mac7119_hashes);*p=38;return 0;}
static void reset(void){tick=clock_tick;log_fail=arm_fail=hash_change=arm_calls=0;export_delay=0;gate7113_cancel();keys=prepare_fail=read_fail=report_fail=export_fail=export_calls=release_count=stage=0;state=0x800032ceU;advance=1149;native_keys=65535;mac7119_have=mac7119_enabled_flag=mac7119_active=mac7119_inflight=0;mac7119_last_nonce=0;memset(saved_report,0,sizeof(saved_report));Snapshot7116Meta m={.search_id=1234,.advance=advance,.seed=state&65535,.hz=clock_hz,.clock_tick=tick,.clock_ms=clock_ms};uint32_t h[4]={11,22,33,44};mac7119_exported(&m,h);assert(!gate7119_enable());}
static void checksum(void){request[31]=mac7119_checksum(request,124);}
static void wide_req(unsigned i,uint64_t v){request[i]=v;request[i+1]=v>>32;}
static void make_request(unsigned frames){memset(request,0,128);memcpy(request,"S7120REQ",8);request[2]=2;request[3]=128;wide_req(4,100);wide_req(6,mac7119_meta.search_id);request[8]=mac7119_meta.advance;request[9]=mac7119_meta.seed;request[10]=frames;request[11]=30;wide_req(12,tick+6000ULL*clock_hz);memcpy(request+14,mac7119_hashes,16);wide_req(19,tick+10ULL*clock_hz);request[21]=clock_hz/200;checksum();}
static void arm_request(void){make_request(0);request[18]=1;request[19]=request[20]=request[21]=0;request[22]=0x7aaa;uint64_t l=tick+60ULL*clock_hz;wide_req(23,l);uint64_t c=(l+5ULL*clock_hz)/4481233ULL+1;c+=(14-c%16)%16;wide_req(25,c*4481233ULL);checksum();}
static unsigned poll(void){unsigned release=gate7119_poll(keys);if(release){release_count++;advance++;state++;}return release;}

static void finish_grid(unsigned jitter){
 unsigned bound=0;
 while(gate7119_running()){
  assert(++bound<65538);
  tick=mac7119_next+jitter;
  poll();
 }
}
int main(int argc,char**argv){
 unsigned ns[]={1,2,8,32,1024,31955,65535};
 for(unsigned mode=0;mode<2;mode++)for(unsigned i=0;i<7;i++){
  reset();make_request(ns[i]);request[11]=mode?60:30;checksum();assert(!poll()&&gate7119_running());
  uint64_t start=mac7120_start;finish_grid(clock_hz/500);
  assert(release_count==ns[i]&&!mac7119_error&&mac7119_sample_count==ns[i]+1&&export_calls==2);
  for(unsigned j=0;j<ns[i];j++)assert(mac7119_samples[j].release_tick==start+(uint64_t)j*clock_hz/request[11]+clock_hz/500);
  assert(!mac7119_samples[ns[i]].release_tick);
  for(unsigned j=0;j<3;j++){tick+=clock_hz;assert(!poll());}assert(release_count==ns[i]);
 }
 reset();make_request(65536);assert(!poll()&&!release_count&&mac7119_error==22);
 reset();make_request(0);assert(!poll()&&!release_count&&mac7119_error==22);
 reset();make_request(8);assert(!poll());tick=mac7119_next+mac7120_late+1;assert(!poll());assert(!poll()&&!gate7119_running()&&mac7119_error==72&&!release_count);
 reset();make_request(8);assert(!poll());tick=mac7119_next;assert(poll());tick=mac7119_next+mac7120_late+1;assert(!poll());assert(!poll()&&!gate7119_running()&&mac7119_error==72&&release_count==1);
 reset();make_request(8);assert(!poll());tick=mac7119_next;assert(poll());keys=1;assert(!poll()&&mac7119_error==53);keys=0;assert(!poll()&&!gate7119_running()&&release_count==1);
 reset();make_request(8);report_fail=1;assert(!poll()&&!release_count&&!gate7119_running());
 reset();make_request(8);export_delay=11ULL*clock_hz;assert(!poll());assert(!poll());assert(!poll()&&!release_count&&mac7119_error==72);
 reset();make_request(2);assert(!poll());log_fail=1;finish_grid(0);assert(mac7119_error==71&&release_count==2&&strstr(saved_report,"aborted"));
 reset();make_request(2);request[14]++;checksum();assert(!poll()&&mac7119_error==23&&!release_count);
 reset();make_request(2);request[18]=2;checksum();assert(!poll()&&mac7119_error==22);
 reset();make_request(2);request[27]=1;checksum();assert(!poll()&&mac7119_error==22);
 reset();arm_request();assert(!poll()&&!gate7119_enabled()&&!release_count&&selected==0x7aaa&&committed&&arm_calls==1);assert(strstr(saved_report,"\"phase\":\"armed\"")&&strstr(saved_report,"\"encounter_launch_armed\":true"));
 reset();arm_request();request[22]=0x7aab;checksum();assert(!poll()&&mac7119_error==22&&!committed&&!arm_calls);
 reset();arm_request();request[25]++;checksum();assert(!poll()&&mac7119_error==25&&!committed);
 reset();arm_request();hash_change=1;assert(!poll()&&mac7119_error==80&&!committed&&!arm_calls);
 reset();arm_request();arm_fail=1;assert(!poll()&&mac7119_error==82&&!committed&&gate7119_enabled());
 reset();arm_request();report_fail=1;assert(!poll()&&mac7119_error==81&&!committed&&!arm_calls);
 reset();arm_request();export_delay=51ULL*clock_hz;assert(!poll()&&mac7119_error==80&&!committed&&!arm_calls);
 reset();make_request(32);assert(!poll());finish_grid(0);FILE*f=fopen(argv[1],"w");assert(f&&fputs(saved_report,f)>=0&&!fclose(f));
 puts("PASS: absolute grid 1..65535 both cadences without accumulated jitter, late abort/no catch-up, keys, one-shot, failed report/export/log, separate physical-UP arm and stale/invalid rejection");
}
