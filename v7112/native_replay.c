#include <unicorn/unicorn.h>
#include <unicorn/arm.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <time.h>
#define NP (1<<20)
static uc_engine *u;
static uint8_t *known[NP],mapped[NP],full[NP];
static int failed=0,frame=0,divcount=0,normals=0,finals=0,lcd=0,lcdlong=0,timers=0,rtc_calls=0;
static uint32_t io;
static uint64_t fixed_rtc,launch_tick;
static int resolving_rtc=0;
static int initializing=1;
static void memory(uc_engine *,uc_mem_type,uint64_t,int,int64_t,void *);
static FILE *ev,*fs;
static uint32_t word(uint32_t a){uint32_t x=0;uc_mem_read(u,a,&x,4);return x;}
static uint8_t byte(uint32_t a){uint8_t x=0;uc_mem_read(u,a,&x,1);return x;}
static uint32_t reg(int r){uint32_t x=0;uc_reg_read(u,r,&x);return x;}
static void setreg(int r,uint32_t x){uc_reg_write(u,r,&x);}
static void setword(uint32_t a,uint32_t x){uc_mem_write(u,a,&x,4);}
static void mark(uint32_t a,size_t n){for(size_t i=0;i<n;i++){uint32_t p=(a+i)>>12;if(!known[p])known[p]=calloc(4096,1);known[p][(a+i)&4095]=1;}}
static void map(uint32_t a,size_t n){uint64_t end=(uint64_t)a+n;for(uint64_t p=a&~4095U;p<end;p+=4096)if(!mapped[p>>12]){uc_err e=uc_mem_map(u,p,4096,UC_PROT_ALL);if(e){fprintf(stderr,"map error %x %s\n",(unsigned)p,uc_strerror(e));exit(2);}mapped[p>>12]=1;if(!initializing){uc_hook h;uc_hook_add(u,&h,UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory,NULL,p,p+4095);}}}
static bool valid(uint32_t a,int n){uint32_t p=a>>12;if((a&4095)+n<=4096){if(full[p])return true;if(!known[p])return false;for(int i=0;i<n;i++)if(!known[p][(a&4095)+i])return false;return true;}for(int i=0;i<n;i++)if(!valid(a+i,1))return false;return true;}
static void memory(uc_engine *uc,uc_mem_type type,uint64_t a,int n,int64_t value,void *d){
 if(type==UC_MEM_WRITE){if(!valid(a,n))mark(a,n);return;}
 if(!valid(a,n)){fprintf(stderr,"UNKNOWN READ %08llX size %d ARM %08X guest %04X frame %d\n",a,n,reg(UC_ARM_REG_PC),word(0x22f5fc)&65535,frame);failed=1;uc_emu_stop(u);}
}
static bool invalid(uc_engine *uc,uc_mem_type type,uint64_t a,int n,int64_t value,void *d){
 if(type==UC_MEM_WRITE_UNMAPPED){map(a,n);return true;}
 fprintf(stderr,"UNMAPPED %08llX size %d type %d ARM %08X guest %04X frame %d\n",a,n,type,reg(UC_ARM_REG_PC),word(0x22f5fc)&65535,frame);failed=1;return false;
}
static void code(uc_engine *uc,uint64_t a,uint32_t n,void *d){
 if(a==0x178abc&&!resolving_rtc){setreg(UC_ARM_REG_R0,(uint32_t)fixed_rtc);setreg(UC_ARM_REG_R1,fixed_rtc>>32);setreg(UC_ARM_REG_PC,reg(UC_ARM_REG_LR));rtc_calls++;}
 else if(a==0x1a7584 && getenv("HEADLESS")){setreg(UC_ARM_REG_PC,reg(UC_ARM_REG_LR));}
 else if(a==0x19cd10 && !(byte(io+2)&128)){setreg(UC_ARM_REG_R0,1);setreg(UC_ARM_REG_PC,reg(UC_ARM_REG_LR));}
 else if(a==0x14aa9c){setreg(UC_ARM_REG_PC,0x169018);}
 else if(a==0x1af11c){
  uint32_t p=word(0x22f5fc)&65535,addr=reg(UC_ARM_REG_R0);
  if(addr==0xffc6&&p==0x554){lcd++;if(byte(io+0xc6))lcdlong++;}
  if(addr==0xffe9&&p==0x3e25)timers++;
  if(addr==0xff04&&(p==0x2b6||p==0x2be||p==0x2f60||p==0x2f68)){
   uint32_t e=word(0x22f604),rem=word(0x22fa50);uint8_t dv=byte(io+4);
   fprintf(ev,"%d,%d,%04X,%02X%02X,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",divcount,frame,p,byte(io+0xe1),byte(io+0xe2),dv,e,rem,(dv*64+64-rem+e)&16383,lcd,lcdlong,timers,byte(io+5),word(0x22fa48),word(0x22f600));divcount++;
   if(p==0x2b6)normals++;if(p==0x2f68)finals++;
  }
 }
}
static void intr(uc_engine *uc,uint32_t number,void *d){
 uint32_t pc=reg(UC_ARM_REG_PC);
 if(resolving_rtc && number==2 && pc==0x1414b8 && word(pc-4)==0xef000028){setreg(UC_ARM_REG_R0,(uint32_t)launch_tick);setreg(UC_ARM_REG_R1,launch_tick>>32);return;}
 fprintf(stderr,"UNSUPPORTED HOST INTERRUPT %u ARM %08X\n",number,pc);failed=1;uc_emu_stop(u);
}
int main(int argc,char **argv){
 if(argc!=4){fprintf(stderr,"usage: replay PRE.bin out-prefix maxframes\n");return 2;}
 uc_err err=uc_open(UC_ARCH_ARM,UC_MODE_ARM,&u);if(err)return 2;
 FILE *f=fopen(argv[1],"rb");if(!f)return 2;uint32_t hdr[2];
 while(fread(hdr,8,1,f)==1){uint32_t a=hdr[0],n=hdr[1];uint8_t *b=malloc(n);if(fread(b,n,1,f)!=1)return 2;map(a,n);uc_mem_write(u,a,b,n);mark(a,n);for(uint64_t p=(a+4095ULL)&~4095ULL;p+4096<=(uint64_t)a+n;p+=4096)full[p>>12]=1;free(b);}fclose(f);
 map(0x7000000,0x10000);mark(0x7000000,0x10000);for(int i=0;i<16;i++)full[0x7000+i]=1;
 setreg(UC_ARM_REG_C1_C0_2,0xf00000);setreg(UC_ARM_REG_FPEXC,0x40000000);io=word(0x22f6d8)-128;
 uint32_t rp=word(0x22f644);fixed_rtc=((uint64_t)word(rp+4)<<32)|word(rp);
 const char *delta=getenv("RTC_DELTA");if(delta){
  struct tm t={0};t.tm_year=(fixed_rtc>>26)-1900;t.tm_mon=((fixed_rtc>>22)&15)-1;t.tm_mday=(fixed_rtc>>17)&31;t.tm_hour=(fixed_rtc>>12)&31;t.tm_min=(fixed_rtc>>6)&63;t.tm_sec=fixed_rtc&63;
  time_t x=timegm(&t)+atoi(delta);gmtime_r(&x,&t);
  fixed_rtc=((uint64_t)(t.tm_year+1900)<<26)|((uint64_t)(t.tm_mon+1)<<22)|((uint64_t)t.tm_mday<<17)|((uint64_t)t.tm_hour<<12)|((uint64_t)t.tm_min<<6)|t.tm_sec;
 }
 char path[1024];snprintf(path,sizeof(path),"%s_events.csv",argv[2]);ev=fopen(path,"w");snprintf(path,sizeof(path),"%s_frames.csv",argv[2]);fs=fopen(path,"w");
 fprintf(ev,"index,frame,pc,state,div,elapsed,remaining,phase,lcd,lcdlong,timer,tima,timer_remaining,budget\n");fprintf(fs,"frame,pc,state,joy_a2,joy_a3,joy_a4,joy_a5,joy_a6,joy_a7,joy_a8,joy_a9,normal,final,div,elapsed,remaining,cpu,hram,audio,gb_stack\n");
 uc_hook h;initializing=0;
 for(uint32_t p=0;p<NP;p++)if(mapped[p]&&!full[p]){bool all=true;for(int i=0;i<4096;i++)if(!known[p]||!known[p][i]){all=false;break;}if(all)full[p]=1;else uc_hook_add(u,&h,UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,memory,NULL,(uint64_t)p<<12,((uint64_t)p<<12)+4095);}
 uc_hook_add(u,&h,UC_HOOK_MEM_UNMAPPED,invalid,NULL,1,0);
 uint32_t hooks[]={0x178abc,0x19cd10,0x14aa9c,0x1af11c,0x1a7584};for(int i=0;i<5;i++)uc_hook_add(u,&h,UC_HOOK_CODE,code,NULL,hooks[i],hooks[i]);
 const char *rtcfile=getenv("RTC_INPUT_FILE");
 if(rtcfile){
  FILE *rf=fopen(rtcfile,"rb");uint64_t ticks[2];uint8_t reference[4096];if(!rf||fread(ticks,16,1,rf)!=1||fread(reference,4096,1,rf)!=1||fgetc(rf)!=EOF)return 2;fclose(rf);
  map(0x1ff81000,4096);uc_mem_write(u,0x1ff81000,reference,4096);mark(0x1ff81000,4096);full[0x1ff81]=1;
  launch_tick=ticks[1];uc_hook_add(u,&h,UC_HOOK_INTR,intr,NULL,1,0);resolving_rtc=1;
  setreg(UC_ARM_REG_SP,0x700fff0);setreg(UC_ARM_REG_LR,0x7000000);
  err=uc_emu_start(u,0x178abc,0x7000000,10000000,0);
  if(err||failed||reg(UC_ARM_REG_PC)!=0x7000000){fprintf(stderr,"RTC resolution failed %s ARM %08X\n",uc_strerror(err),reg(UC_ARM_REG_PC));return 2;}
  fixed_rtc=((uint64_t)reg(UC_ARM_REG_R1)<<32)|reg(UC_ARM_REG_R0);resolving_rtc=0;
  fprintf(stderr,"RTC_INPUT_RESOLVED %016llX tick %llu\n",fixed_rtc,launch_tick);
 }
 int max=atoi(argv[3]);
 for(frame=0;frame<max;frame++){
  setreg(UC_ARM_REG_SP,0x700ffc8);setword(0x700ffec,0x7000000);setreg(UC_ARM_REG_LR,0x7000000);setreg(UC_ARM_REG_R0,word(word(0x1a857c)));
  if(frame){uint16_t pad=(frame==1||frame==2)?0xffbf:0xffff;uc_mem_write(u,0x22f766,&pad,2);}
  err=uc_emu_start(u,0x1a824c,0x7000000,10000000,0);
  fprintf(fs,"%d,%04X,%02X%02X",frame,word(0x22f5fc)&65535,byte(io+0xe1),byte(io+0xe2));for(int i=0;i<8;i++)fprintf(fs,",%02X",byte(io+0xa2+i));fprintf(fs,",%d,%d,%u,%u,%u,",normals,finals,byte(io+4),word(0x22f604),word(0x22fa50));for(int i=0;i<64;i++)fprintf(fs,"%02X",byte(0x22f5e0+i));fprintf(fs,",");for(int i=0;i<127;i++)fprintf(fs,"%02X",byte(io+128+i));fprintf(fs,",");for(int i=0;i<448;i++)fprintf(fs,"%02X",byte(word(0x22f6c8)+256+i));fprintf(fs,",");for(int i=0;i<256;i++)fprintf(fs,"%02X",byte(word(0x22f6c8)+i));fprintf(fs,"\n");
  if(err||failed||reg(UC_ARM_REG_PC)!=0x7000000||finals>=3)break;
  if(frame%100==99){fprintf(stderr,"frame %d normal %d final %d\n",frame+1,normals,finals);fflush(ev);fflush(fs);}
 }
 fclose(ev);fclose(fs);fprintf(stderr,"END frame %d normal %d final %d RTC %d ARM %08X error %s failed %d\n",frame,normals,finals,rtc_calls,reg(UC_ARM_REG_PC),uc_strerror(err),failed);uc_close(u);return err||failed;
}
