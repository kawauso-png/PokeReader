#include "shadow.h"
#include "dv_endpoint.h"
#include <stdlib.h>
#include <string.h>
#include <time.h>
/* Specialize callback targets inside the hot interpreter loop. */
#define ARM7113_API static inline __attribute__((always_inline))
#define arm7113_step shadow_arm_inline
#ifdef __3DS__
#include "v7113_arm_core.c"
#else
#include "arm_core.c"
#endif
#undef arm7113_step
#undef ARM7113_API
static const Shadow7113Input *in;
static Arm7113 cpu;
static unsigned fail,frame,normals,finals,divs,lcd,lcdlong,timer;
static uint32_t io,dv_bank;static DvEndpoint7115 endpoint;
static uint8_t stack[65536];
typedef struct {uint32_t base;uint8_t*data,*known;} Extra;
static Extra extra[128];static unsigned nextra;
static uint8_t*view(uint32_t addr,unsigned n,int write){
 if(n!=1&&n!=2&&n!=4){fail=100;return NULL;}
 if(addr>UINT32_MAX-(n-1)){fail=101;return NULL;}
 if(addr>=0x1b1000&&addr<=0x300000-n)return in->static_data+addr-0x1b1000;
 if(addr>=in->heap_base&&addr-in->heap_base<=0x100000-n)return in->heap_data+addr-in->heap_base;
 if(addr>=0x7000000&&addr<=0x7010000-n)return stack+addr-0x7000000;
 if(addr>=0x100000&&addr<=0x1b1000-n){if(write){fail=102;return NULL;}return (uint8_t*)in->code+addr-0x100000;}
 if(addr>=in->rom_base&&addr-in->rom_base<=in->rom_size-n){if(write){fail=103;return NULL;}return (uint8_t*)in->rom+addr-in->rom_base;}
 if((addr&4095)+n>4096){fail=104;return NULL;}
 Extra*p=NULL;for(unsigned j=0;j<nextra;j++)if(extra[j].base==(addr&~4095U)){p=&extra[j];break;}
 if(!p&&write&&nextra<128){p=&extra[nextra++];p->base=addr&~4095U;p->data=calloc(4096,1);p->known=calloc(4096,1);}
 if(!p||!p->data||!p->known){fail=105;return NULL;}
 unsigned off=addr&4095;
 for(unsigned j=0;j<n;j++){if(write)p->known[off+j]=1;else if(!p->known[off+j]){fail=106;return NULL;}}
 return p->data+off;
}
static uint32_t readmem(uint32_t addr,unsigned n){
 if(n==4&&(addr&3)==0&&addr>=0x100000&&addr<0x1b1000&&((uintptr_t)in->code&3)==0)return ((const uint32_t*)in->code)[(addr-0x100000)>>2];
 uint8_t*p=view(addr,n,0);if(!p)return 0;
 if(n==1)return *p;
 if(n==4&&((uintptr_t)p&3)==0)return *(const uint32_t*)p;
 if(n==2&&((uintptr_t)p&1)==0)return *(const uint16_t*)p;
 uint32_t v=(uint32_t)p[0]|(uint32_t)p[1]<<8;
 return n==4?v|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24:v;
}
static void writemem(uint32_t addr,uint32_t v,unsigned n){
 uint8_t*p=view(addr,n,1);if(!p)return;
 if(n==1)*p=v;
 else if(n==4&&((uintptr_t)p&3)==0)*(uint32_t*)p=v;
 else if(n==2&&((uintptr_t)p&1)==0)*(uint16_t*)p=v;
 else {p[0]=v;p[1]=v>>8;if(n==4){p[2]=v>>16;p[3]=v>>24;}}
 if(addr==0x22f768&&n==4)dv_bank=v;
 if(n==1&&(addr==dv_bank+0x23d||addr==dv_bank+0x23e))
  dv7115_observe(&endpoint,dv_bank,addr,n,v,readmem(0x22f5fc,2),readmem(io+0x9d,1),frame);
}
static int hook(void){uint32_t a=cpu.r[15];if(a==0x178abc){uint64_t rtc=in->rtc(frame,in->opaque);cpu.r[0]=rtc;cpu.r[1]=rtc>>32;cpu.r[15]=cpu.r[14];return 1;}if(a==0x1a7584){cpu.r[15]=cpu.r[14];return 1;}if(a==0x19cd10&&!(readmem(io+2,1)&128)){cpu.r[0]=1;cpu.r[15]=cpu.r[14];return 1;}if(a==0x14aa9c){cpu.r[15]=0x169018;return 1;}
 if(a==0x1af11c){uint32_t p=readmem(0x22f5fc,4)&65535,addr=cpu.r[0];if(addr==0xffc6&&p==0x554){lcd++;if(readmem(io+0xc6,1))lcdlong++;}if(addr==0xffe9&&p==0x3e25)timer++;
 if(addr==0xff04&&(p==0x2b6||p==0x2be||p==0x2f60||p==0x2f68)){unsigned e=readmem(0x22f604,4),rem=readmem(0x22fa50,4),dv=readmem(io+4,1);if(in->event)in->event(frame,p,(readmem(io+0xe1,1)<<8)|readmem(io+0xe2,1),dv,e,rem,lcd,lcdlong,timer,in->opaque);
 divs++;if(p==0x2b6)normals++;if(p==0x2f68)finals++;}}
 return 0;}

Shadow7113Result shadow7113_run(const Shadow7113Input *input,unsigned maxframes){
 in=input;memset(&cpu,0,sizeof(cpu));memset(stack,0,sizeof(stack));memset(&endpoint,0,sizeof(endpoint));
 fail=normals=finals=divs=lcd=lcdlong=timer=0;nextra=0;
 io=readmem(0x22f6d8,4)-128;dv_bank=readmem(0x22f768,4);
 for(frame=0;frame<maxframes;frame++){
  cpu.r[13]=0x700ffc8;writemem(0x700ffec,0x7000000,4);cpu.r[14]=0x7000000;cpu.r[0]=readmem(readmem(0x1a857c,4),4);cpu.r[15]=0x1a824c;
  if(frame)writemem(0x22f766,frame==1||frame==2?0xffbf:0xffff,2);
  unsigned local=0;
  while(cpu.r[15]!=0x7000000&&!cpu.error&&!fail){if(!hook())shadow_arm_inline(&cpu,readmem,writemem);if(++local>10000000){fail=107;break;}}
  if(cpu.error||fail||endpoint.mask==3)break;
  if(in->progress&&!in->progress(frame,cpu.steps,in->opaque)){fail=108;break;}
 }
 Shadow7113Result r={0};r.error=fail?fail:cpu.error;r.arm_pc=cpu.error?cpu.error_pc:cpu.r[15];r.arm_op=cpu.error_op;r.guest_pc=readmem(0x22f5fc,4)&65535;r.frame=frame;r.normal=normals;r.final=finals;r.reads=divs;r.lcd=lcd;r.lcdlong=lcdlong;r.timer=timer;r.instructions=cpu.steps;
 r.dv_write_mask=endpoint.mask;r.dv_write_frame=endpoint.frame;
 if(endpoint.mask==3&&!r.error){
  unsigned actual=(readmem(endpoint.base+0x23d,1)<<8)|readmem(endpoint.base+0x23e,1);
  if(fail)r.error=fail;
  else if(actual!=endpoint.dv)r.error=111;
  else {r.dv=actual;r.shiny=(r.dv&0xfff)==0xaaa&&((r.dv>>12)&2);}
 }else if(maxframes>=1000&&!r.error)r.error=110;
 for(unsigned j=0;j<nextra;j++){free(extra[j].data);free(extra[j].known);}nextra=0;
 return r;
}
uint64_t shadow7113_pack_ms(uint64_t ms){
 /* 1900 epoch; integer UTC conversion, no dependence on Mac/3DS timezone. */
 uint64_t sec=ms/1000;uint32_t days=sec/86400,year=1900;sec%=86400;
 for(;;){unsigned leap=(year%4==0&&(year%100!=0||year%400==0)),n=365+leap;if(days<n)break;days-=n;if(++year>4095)return 0;}
 static const unsigned mdays[]={31,28,31,30,31,30,31,31,30,31,30,31};unsigned month=0;
 while(month<11){unsigned n=mdays[month]+(month==1&&(year%4==0&&(year%100!=0||year%400==0)));if(days<n)break;days-=n;month++;}
 return (uint64_t)year<<26|(uint64_t)(month+1)<<22|(uint64_t)(days+1)<<17|(sec/3600)<<12|((sec/60)%60)<<6|(sec%60);
}
