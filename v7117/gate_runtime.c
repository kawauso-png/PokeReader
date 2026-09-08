/* Only run while the real guest is paused. Native/ROM pointers are read-only;
 * the simulator borrows the existing private snapshot buffer and recaptures
 * it before every hypothesis and before actual input. */
#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include "pnp.h"
#include "hid.h"
#include "rank_runtime.h"
#include "rank_core.h"
#include "gate_runtime.h"
#include "shadow.h"
#include "snapshot.h"
#include "prefix.h"
extern uint8_t*suicune_shadow7113_capture(uint32_t,uint32_t*);
extern uint32_t suicune_native_pre_state(uint32_t*);
extern void host7113_progress(uint32_t,uint32_t,uint32_t);
extern void host7117_stage(uint32_t);
extern uint32_t host_trace_file_write(const char*,uint32_t);
static uint32_t error,checks,advance,seed,selected,models,profile,committed;
static uint32_t lead_seconds=300,bench_ready;
static uint64_t search_id,launch,resume,clock_ms,clock_tick;static uint32_t clock_hz;
static Shadow7113Result results[2],bench_result;
static uint64_t bench_elapsed,bench_seconds,snapshot_ticks;
static uint32_t snapshot_saved,snapshot_hashes[4],ever_dumped;
static uint32_t prefix_offers[2],prefix_state[2],prefix_phase[2],prefix_seen[2],prefix_models;
static Shadow7113Result prefixes[2];
#ifdef GATE7113_TEST
extern uint32_t gate_test_read(uint32_t,unsigned);
static uint32_t word(uint32_t a){return gate_test_read(a,4);}
static uint8_t byte(uint32_t a){return gate_test_read(a,1);}
#else
static uint32_t word(uint32_t a){return *(const volatile uint32_t*)a;}
static uint8_t byte(uint32_t a){return *(const volatile uint8_t*)a;}
#endif
static uint64_t wide(uint32_t a){return (uint64_t)word(a)|(uint64_t)word(a+4)<<32;}
static uint64_t ms_at(uint64_t tick){return clock_ms+(tick-clock_tick)/clock_hz*1000+((tick-clock_tick)%clock_hz)*1000/clock_hz;}
static int clock_capture(void){
 if(!is_memory_mapped(0x1ff81000)||!is_memory_mapped(0x1ff81fff))return 0;
 for(unsigned i=0;i<3;i++){
  uint32_t v=word(0x1ff81000),a=0x1ff81020+(v&1)*32;
  uint64_t ms=wide(a),ref=wide(a+8);uint32_t hz=word(a+16);int64_t drift=(int64_t)wide(a+24);uint64_t now=svcGetSystemTick();
  if(word(0x1ff81000)!=v||hz!=268111856U||now<ref)continue;
  clock_ms=ms+drift+(now-ref)/hz*1000+((now-ref)%hz)*1000/hz;clock_tick=now;clock_hz=hz;return 1;
 }return 0;
}
static uint64_t packed_seconds(uint64_t p){unsigned year=p>>26,month=(p>>22)&15,day=(p>>17)&31,h=(p>>12)&31,m=(p>>6)&63,s=p&63;if(year<1900||year>4095||month<1||month>12||day<1||day>31||h>23||m>59||s>59)return 0;unsigned days=0;for(unsigned y=1900;y<year;y++)days+=365+(y%4==0&&(y%100!=0||y%400==0));static const unsigned md[]={31,28,31,30,31,30,31,31,30,31,30,31};for(unsigned mo=1;mo<month;mo++)days+=md[mo-1]+(mo==2&&(year%4==0&&(year%100!=0||year%400==0)));return (uint64_t)(days+day-1)*86400+h*3600+m*60+s;}
static uint64_t rtc(unsigned f,void*unused){unsigned fps=profile==0?30:60;uint64_t tick=f<3?launch+(uint64_t)f*clock_hz/fps:resume+(uint64_t)(f-3)*clock_hz/fps;return shadow7113_pack_ms(ms_at(tick));}
static int progress(unsigned f,uint64_t steps,void*unused){
 if((f&15)==0){scan_input();if(get_current_keys()&KEY_SELECT){error=0x711301;return 0;}host7113_progress(checks,profile,f);}
 if(svcGetSystemTick()+2ULL*clock_hz>=launch){error=0x711302;return 0;}return 1;
}
static void prefix_event(unsigned f,unsigned pc,unsigned state,unsigned div,unsigned elapsed,unsigned rem,unsigned lcd,unsigned longlcd,unsigned timer,void*unused){
 if(f>=64&&pc==0x2b6&&!prefix_seen[profile]){prefix_seen[profile]=1;prefix_state[profile]=state;prefix_phase[profile]=(div*64+64-rem+elapsed)&16383;}
}
static void save_input(uint8_t*data,uint32_t heap){
 Snapshot7116Meta meta={.search_id=search_id,.clock_ms=clock_ms,.clock_tick=clock_tick,.launch=launch,.resume=resume,.check=checks,.advance=advance,.seed=seed,.rom_base=word(0x22f6c4),.rom_size=2097152,.heap_base=heap,.hz=clock_hz};
 uint64_t saved_at=svcGetSystemTick();snapshot_saved=snapshot7116_save(&meta,(const uint8_t*)0x100000,data,(const uint8_t*)meta.rom_base,snapshot_hashes);snapshot_ticks=svcGetSystemTick()-saved_at;if(snapshot_saved)ever_dumped=1;
}
unsigned gate7117_offers(void){return prefix_offers[0]+prefix_offers[1];}
int gate7117_selected_pre(uint32_t target,uint32_t state){return selected&&committed&&target==advance&&state==seed;}
void gate7113_begin(void){ever_dumped=0;memset(&bench_result,0,sizeof(bench_result));bench_elapsed=bench_seconds=0;lead_seconds=300;bench_ready=0;error=checks=selected=models=committed=0;launch=resume=0;search_id=svcGetSystemTick();rank7108_begin();}
uint32_t gate7113_error(void){return error;}
uint32_t gate7113_checks(void){return checks;}
uint32_t gate7113_dv(void){return selected;}
uint32_t gate7113_models(void){return models;}
uint64_t gate7113_launch_tick(void){return launch;}
uint64_t gate7113_resume_tick(void){return resume;}
int gate7113_active(void){return selected!=0;}
void gate7113_cancel(void){selected=models=committed=0;launch=resume=0;}
int gate7113_evaluate(void){
 checks++;error=selected=models=committed=0;prefix_models=0;memset(prefixes,0,sizeof(prefixes));memset(prefix_offers,0,sizeof(prefix_offers));memset(prefix_seen,0,sizeof(prefix_seen));memset(prefix_state,0,sizeof(prefix_state));memset(prefix_phase,0,sizeof(prefix_phase));snapshot_saved=0;snapshot_ticks=0;memset(snapshot_hashes,0,sizeof(snapshot_hashes));memset(results,0,sizeof(results));
 uint32_t st=suicune_native_pre_state(&advance);seed=st&65535;if(!(st&0x80000000U)){error=0x711303;return -1;}
 /* All input-neutral PRE phases are eligible; historical ranks do not reject them. */
 for(uint32_t a=0x100000;a<0x1b1000;a+=4096)if(!is_memory_mapped(a)){error=0x711312;return -1;}
 plan_again:
 if(!clock_capture()){error=0x711304;return -1;}
 uint32_t heap=0;uint8_t*data=suicune_shadow7113_capture(advance,&heap);if(!data){error=0x711305;return -1;}
 uint32_t rp=word(0x22f644),rawp=word(0x22f640);
 if(!is_memory_mapped(rp)||!is_memory_mapped(rp+7)||!is_memory_mapped(rawp)){error=0x711306;return -1;}
 uint64_t oldsec=packed_seconds(wide(rp));unsigned raw=byte(rawp);
 if(!oldsec||raw>=60){error=0x711307;return -1;}
 /* Reserve enough host time to compute; target natural guest RTC second 10
  * to keep the modeled event away from minute rollovers. No RTC is changed. */
 uint64_t sec=clock_ms/1000+lead_seconds;if(sec<oldsec){error=0x711308;return -1;}
 unsigned rawsec=(raw+(sec-oldsec)%60)%60;sec+=(70-rawsec)%60;
 uint64_t delta_ms=sec*1000+500-clock_ms;launch=clock_tick+delta_ms*clock_hz/1000;
 uint64_t cycle=(launch+5ULL*clock_hz)/4481233ULL+1;while((cycle&15)!=14)cycle++;resume=cycle*4481233ULL;
 if(!bench_ready){
  host7117_stage(2);profile=0;Shadow7113Input in={0};in.code=(const uint8_t*)0x100000;in.rom_base=word(0x22f6c4);in.rom=(const uint8_t*)in.rom_base;in.rom_size=2097152;in.heap_base=heap;in.static_data=data;in.heap_data=data+0x14f000;in.rtc=rtc;in.progress=progress;
  uint64_t start=svcGetSystemTick();Shadow7113Result b=shadow7113_run(&in,20);uint64_t elapsed=svcGetSystemTick()-start;bench_result=b;bench_elapsed=elapsed;
  if(b.error||!b.instructions){results[0]=b;if(!error)error=0x711400+b.error;return -1;}
  uint64_t estimate=(elapsed/b.instructions)*700000000ULL+(elapsed%b.instructions)*700000000ULL/b.instructions;
  uint64_t seconds=estimate/clock_hz+20;bench_seconds=seconds;if(seconds<30)seconds=30;if(seconds>900){error=0x711314;return -1;}
  lead_seconds=seconds;bench_ready=1;goto plan_again;
 }
 /* The first input is saved even when no suffix is proposed. Later complete
  * checks and errors replace it. All models always start from a fresh copy. */
 if(!ever_dumped)save_input(data,heap);host7117_stage(1);
 for(profile=0;profile<2;profile++){
  if(profile){data=suicune_shadow7113_capture(advance,&heap);if(!data){error=0x711305;return -1;}}
  Shadow7113Input pre={0};pre.code=(const uint8_t*)0x100000;pre.rom_base=word(0x22f6c4);pre.rom=(const uint8_t*)pre.rom_base;pre.rom_size=2097152;pre.heap_base=heap;pre.static_data=data;pre.heap_data=data+0x14f000;pre.rtc=rtc;pre.progress=progress;pre.event=prefix_event;
  host7113_progress(checks,profile,0);prefixes[profile]=shadow7113_run(&pre,65);
  if(prefixes[profile].error||!prefix_seen[profile]){
   results[profile]=prefixes[profile];if(!error)error=prefixes[profile].error?0x711400+prefixes[profile].error:0x711701;
   data=suicune_shadow7113_capture(advance,&heap);if(data)save_input(data,heap);return -1;
  }
  prefix_offers[profile]=prefix7117_offers(prefix_state[profile],prefix_phase[profile]);
  if(prefix_offers[profile]){prefix_models|=1U<<profile;break;}
 }
 /* Regular complete audits can find candidates omitted by the finite suffix
  * ensemble and provide new outcomes without requiring physical input. */
 if(!prefix_models&&(checks&63U)!=0)return 0;
 data=suicune_shadow7113_capture(advance,&heap);if(!data){error=0x711305;return -1;}save_input(data,heap);host7117_stage(0);
 for(profile=0;profile<2;profile++){
  if(profile){data=suicune_shadow7113_capture(advance,&heap);if(!data){error=0x711305;return -1;}}
  Shadow7113Input in={0};in.code=(const uint8_t*)0x100000;in.rom_base=word(0x22f6c4);in.rom=(const uint8_t*)in.rom_base;in.rom_size=2097152;in.heap_base=heap;in.static_data=data;in.heap_data=data+0x14f000;in.rtc=rtc;in.progress=progress;
  host7113_progress(checks,profile,0);results[profile]=shadow7113_run(&in,1100);
  if(results[profile].error){if(!error)error=0x711400+results[profile].error;selected=models=0;return -1;}
  if(results[profile].shiny){models|=1U<<profile;if(!selected)selected=results[profile].dv;}
 }
 uint32_t now=0,current=suicune_native_pre_state(&now);if(now!=advance||current!=st){error=0x711309;selected=models=0;return -1;}
 return selected?1:0;
}
static int append_file(const char*path,const char*line,int fresh){
 if(R_FAILED(fsInit()))return 0;FS_Archive sd;if(R_FAILED(FSUSER_OpenArchive(&sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){fsExit();return 0;}
 FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/traces"),0);Handle file;Result e=FSUSER_OpenFile(&file,sd,fsMakePath(PATH_ASCII,path),FS_OPEN_WRITE|FS_OPEN_CREATE,0);FSUSER_CloseArchive(sd);if(R_FAILED(e)){fsExit();return 0;}uint64_t n=0;uint32_t wrote=0;int ok=!R_FAILED(FSFILE_GetSize(file,&n))&&(!fresh||!n);unsigned len=strlen(line);
 if(ok)ok=!R_FAILED(FSFILE_Write(file,&wrote,n,line,len,0))&&wrote==len;
 Result fl=FSFILE_Flush(file),cl=FSFILE_Close(file);fsExit();return ok&&!R_FAILED(fl)&&!R_FAILED(cl);
}
int gate7113_log_scan(int decision){
 char path[160],line[1792];
 snprintf(path,sizeof(path),"/luma/plugins/pokereader/traces/shiny7117_%016llX.csv",(unsigned long long)search_id);
 int used=snprintf(line,sizeof(line),"GATE7117,%u,%u,%04X,%u,%d,%08X,%04X,%u,%04X,%u,%04X,%u,%llu,%llu,%llu\n",checks,advance,seed,0U,decision,error,selected,models,results[0].dv,results[0].error,results[1].dv,results[1].error,(unsigned long long)results[0].instructions,(unsigned long long)launch,(unsigned long long)resume);
 if(used<0||(unsigned)used>=sizeof(line)){error=0x711310;return 0;}
 int n=snprintf(line+used,sizeof(line)-used,"GATE7117_BENCH,%u,%llu,%llu,%llu,%u,%u,%u,%08X,%08X\n",checks,(unsigned long long)bench_elapsed,(unsigned long long)bench_result.instructions,(unsigned long long)bench_seconds,lead_seconds,bench_ready,bench_result.error,bench_result.arm_pc,bench_result.arm_op);
 if(n<0||(unsigned)n>=sizeof(line)-used){error=0x711310;return 0;}used+=n;
 for(unsigned p=0;p<2;p++){
  Shadow7113Result*r=&results[p];n=snprintf(line+used,sizeof(line)-used,"GATE7117_CPU,%u,%u,%u,%08X,%08X,%04X,%u,%u,%u,%u,%llu,%u,%u,%u,%llu,%u,%08X\n",checks,p,r->error,r->arm_pc,r->arm_op,r->guest_pc,r->frame,r->normal,r->final,r->reads,(unsigned long long)r->instructions,r->dv_write_mask,r->dv_write_frame,r->fast_enabled,(unsigned long long)r->fast_steps,r->fast_blocks,r->fast_mismatch);
  if(n<0||(unsigned)n>=sizeof(line)-used){error=0x711310;return 0;}used+=n;
 }
 int sn=snprintf(line+used,sizeof(line)-used,"GATE7117_PRE,%u,%u,%llu,%08X,%08X,%08X,%08X\n",checks,snapshot_saved,(unsigned long long)snapshot_ticks,snapshot_hashes[0],snapshot_hashes[1],snapshot_hashes[2],snapshot_hashes[3]);
 if(sn<0||(unsigned)sn>=sizeof(line)-used){error=0x711310;return 0;}used+=sn;
 for(unsigned p=0;p<2;p++){
  Shadow7113Result*r=&prefixes[p];int pn=snprintf(line+used,sizeof(line)-used,"GATE7117_PREFIX,%u,%u,%u,%04X,%u,%u,%u,%llu,%u,%08X\n",checks,p,prefix_seen[p],prefix_state[p],prefix_phase[p],prefix_offers[p],r->error,(unsigned long long)r->instructions,r->fast_enabled,r->fast_mismatch);
  if(pn<0||(unsigned)pn>=sizeof(line)-used){error=0x711310;return 0;}used+=pn;
 }
 if(!append_file(path,line,checks==1)){error=0x711310;return 0;}return 1;
}
int gate7113_commit(void){uint32_t a=0,s=suicune_native_pre_state(&a);if(!selected||a!=advance||!(s&0x80000000U)||(s&65535)!=seed||svcGetSystemTick()+5ULL*clock_hz>=launch){error=0x711311;return 0;}committed=1;return 1;}
void gate7113_append_result(uint32_t a,uint32_t present,uint32_t dv){if(!committed)return;char line[256];snprintf(line,sizeof(line),"\nGATE7117_RESULT,%u,%u,%04X,%u,%04X,%u,%u\n",advance,a,selected,models,dv,present,a==advance&&present&&dv==selected);host_trace_file_write(line,strlen(line));}
