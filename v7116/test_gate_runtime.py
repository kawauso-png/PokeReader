from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parent
header=r'''#include <stdint.h>
#include <stddef.h>
#include <string.h>
extern char gate_output[2048];
typedef int Result;typedef int Handle;typedef int FS_Archive;
#define KEY_SELECT 2048
#define R_FAILED(x) ((x)<0)
#define ARCHIVE_SDMC 0
#define PATH_EMPTY 0
#define PATH_ASCII 1
#define FS_OPEN_WRITE 1
#define FS_OPEN_CREATE 2
uint64_t svcGetSystemTick(void);
static inline int fsInit(void){return 0;}static inline void fsExit(void){}
static inline int fsMakePath(int a,const char*b){return 0;}
static inline int FSUSER_OpenArchive(int*a,int b,int c){*a=1;return 0;}
static inline int FSUSER_CreateDirectory(int a,int b,int c){return 0;}
static inline int FSUSER_OpenFile(int*a,int b,int c,int d,int e){*a=1;return 0;}
static inline int FSUSER_CloseArchive(int a){return 0;}
static inline int FSFILE_GetSize(int a,uint64_t*b){*b=0;return 0;}
static inline int FSFILE_Write(int a,uint32_t*b,uint64_t c,const void*d,unsigned e,int f){if(e>=2048)return -1;memcpy(gate_output,d,e);gate_output[e]=0;*b=e;return 0;}
static inline int FSFILE_Flush(int a){return 0;}static inline int FSFILE_Close(int a){return 0;}
'''
source=r'''#include <assert.h>
#define GATE7113_TEST
#define shadow7113_run test_shadow_run
#include "gate_runtime.c"
#undef shadow7113_run
char gate_output[2048];static uint64_t bench_extra_ticks;
static uint64_t now=1000000;static unsigned rank=100,calls,bad,change_state;
static uint16_t dvs[2];static unsigned dumps,dump_failure;
int snapshot7116_save(const Snapshot7116Meta*m,const uint8_t*c,const uint8_t*d,const uint8_t*r,uint32_t*h){assert(calls==1&&m->advance==473&&m->seed==0x14ad&&m->hz==268111856&&m->launch>m->clock_tick);dumps++;for(unsigned i=0;i<4;i++)h[i]=i+1;return !dump_failure;}
uint64_t svcGetSystemTick(void){now+=1000;return now;}
uint32_t gate_test_read(uint32_t a,unsigned n){
 uint64_t packed=(uint64_t)2026<<26|9ULL<<22|8ULL<<17|22ULL<<12|9ULL<<6|53;
 uint64_t ms=3997894193000ULL;
 if(a==0x1ff81000)return 0;if(a==0x1ff81020)return ms;if(a==0x1ff81024)return ms>>32;
 if(a==0x1ff81028)return 1000000;if(a==0x1ff8102c)return 0;if(a==0x1ff81030)return 268111856;
 if(a==0x1ff81038||a==0x1ff8103c)return 0;
 if(a==0x22f644)return 0x8a4e060;if(a==0x22f640)return 0x8a4e058;
 if(a==0x8a4e060)return packed;if(a==0x8a4e064)return packed>>32;if(a==0x8a4e058)return 56;
 if(a==0x22f6c4)return 0x8800010;return 0;
}
int is_memory_mapped(uint32_t a){return 1;}
void scan_input(void){}uint32_t get_current_keys(void){return 0;}
uint32_t suicune_rank_pre_state(uint32_t*a){*a=473;return change_state&&calls>=3?0:0x800014ad;}
uint8_t*suicune_shadow7113_capture(uint32_t a,uint32_t*h){static uint8_t x;*h=0x8a00000;return &x;}
void host7113_progress(uint32_t a,uint32_t b,uint32_t c){}
uint32_t host_trace_file_write(const char*a,uint32_t b){return b;}
void rank7108_begin(void){}int rank7108_evaluate(void){return 0;}uint32_t rank7108_error(void){return 1;}uint32_t rank7108_cycles(void){return 9000;}uint32_t rank7108_best_rank(void){return rank;}uint32_t rank7108_support(void){return 1;}
Shadow7113Result test_shadow_run(const Shadow7113Input*i,unsigned frames){Shadow7113Result r={0};r.instructions=5000000;calls++;if(frames==20){now+=bench_extra_ticks;return r;}unsigned index=(calls-2)&1;r.dv=dvs[index];r.shiny=(r.dv&0xfff)==0xaaa&&((r.dv>>12)&2);if(bad&&index==1)r.error=7;return r;}
static void reset(void){dumps=dump_failure=0;now=1000000;bench_extra_ticks=0;calls=bad=change_state=0;rank=100;dvs[0]=dvs[1]=0x43e8;gate7113_begin();}
int main(void){
 reset();bench_extra_ticks=2681118560ULL;assert(gate7113_evaluate()<0&&gate7113_error()==0x711314&&!gate7113_active());assert(gate7113_log_scan(-1));assert(strstr(gate_output,"GATE7116_BENCH,1,")&&strstr(gate_output,",5000000,"));
 reset();rank=9999;assert(gate7113_evaluate()==0&&calls==0&&dumps==0&&!gate7113_active());
 reset();assert(gate7113_evaluate()==0&&calls==3&&dumps==1&&!gate7113_active());
 reset();dvs[0]=0x6aaa;assert(gate7113_evaluate()==1&&gate7113_dv()==0x6aaa&&gate7113_models()==1);assert((gate7113_resume_tick()/4481233)&15U==14U);assert(gate7113_log_scan(1));assert(gate7113_commit());
 reset();dump_failure=1;dvs[0]=0x6aaa;assert(gate7113_evaluate()==1&&dumps==1);assert(gate7113_log_scan(1)&&strstr(gate_output,"GATE7116_PRE,1,0,"));
 reset();dvs[1]=0x2aaa;assert(gate7113_evaluate()==1&&gate7113_dv()==0x2aaa&&gate7113_models()==2);
 reset();dvs[0]=0x6aaa;bad=1;assert(gate7113_evaluate()<0&&!gate7113_active());
 reset();dvs[0]=0x6aaa;change_state=1;assert(gate7113_evaluate()<0&&!gate7113_active());
 reset();dvs[0]=0x6aaa;assert(gate7113_evaluate()==1);now=gate7113_launch_tick();assert(!gate7113_commit());gate7113_cancel();assert(!gate7113_active());
}
'''
# Correct grouping: equality must compare the masked slot, not mask a Boolean.
source=source.replace('assert((gate7113_resume_tick()/4481233)&15U==14U);','assert(((gate7113_resume_tick()/4481233)&15U)==14U);')
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'3ds.h').write_text('#pragma once\n'+header);(d/'pnp.h').write_text('#include <stdint.h>\nint is_memory_mapped(uint32_t);\n');(d/'hid.h').write_text('#include <stdint.h>\nvoid scan_input(void);uint32_t get_current_keys(void);\n');(d/'test.c').write_text(source)
 subprocess.run(['cc','-std=c99','-Wno-int-to-pointer-cast','-I'+str(d),'-I'+str(r),'-I'+str(r.parent/'v7108'),'-I'+str(r.parent/'v7113'),str(d/'test.c'),str(r.parent/'v7113/shadow.c'),str(r.parent/'v7113/arm_core.c'),'-o',str(d/'test')],check=True)
 subprocess.run([str(d/'test')],check=True)
print('PASS: shortlist never selects alone, full replay selects either shiny hypothesis, replay errors/state drift/expired commit cannot select, planned M14 slot; slow benchmark logs measurements and cannot select')
