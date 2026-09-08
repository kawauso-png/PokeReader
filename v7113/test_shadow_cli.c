#include "shadow.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static FILE*events;static uint64_t fixed,schedule[1100];
static uint64_t rtc(unsigned f,void*d){return schedule[f]?schedule[f]:fixed;}
static void event(unsigned f,unsigned pc,unsigned state,unsigned div,unsigned elapsed,unsigned rem,unsigned lcd,unsigned longlcd,unsigned timer,void*d){static unsigned i;fprintf(events,"%u,%u,%04X,%04X,%u,%u,%u,%u,%u,%u,%u\n",i++,f,pc,state,div,elapsed,rem,(div*64+64-rem+elapsed)&16383,lcd,longlcd,timer);}
static void copy(uint32_t a,uint32_t n,const uint8_t*b,uint32_t base,uint32_t size,uint8_t*out){uint64_t lo=a>base?a:base,hi=(uint64_t)a+n<(uint64_t)base+size?(uint64_t)a+n:(uint64_t)base+size;if(lo<hi)memcpy(out+lo-base,b+lo-a,hi-lo);}
int main(int argc,char**argv){if(argc!=5)return 2;Shadow7113Input in={0};in.static_data=calloc(0x14f000,1);in.heap_data=calloc(0x100000,1);in.code=calloc(0xb1000,1);in.rom=calloc(0x200000,1);in.rom_size=0x200000;in.rtc=rtc;in.event=event;
 FILE*f=fopen(argv[1],"rb");if(!f)return 2;
 for(unsigned pass=0;pass<2;pass++){rewind(f);uint32_t h[2];while(fread(h,8,1,f)==1){uint8_t*b=malloc(h[1]);if(fread(b,h[1],1,f)!=1)return 2;copy(h[0],h[1],b,0x1b1000,0x14f000,in.static_data);if(pass){copy(h[0],h[1],b,0x100000,0xb1000,(uint8_t*)in.code);copy(h[0],h[1],b,in.rom_base,in.rom_size,(uint8_t*)in.rom);copy(h[0],h[1],b,in.heap_base,0x100000,in.heap_data);}free(b);}memcpy(&in.rom_base,in.static_data+0x22f6c4-0x1b1000,4);memcpy(&in.heap_base,in.static_data+0x22f6c8-0x1b1000,4);in.heap_base&=0xfff00000;}
 fclose(f);fixed=strtoull(argv[2],NULL,16);const char*s=getenv("RTC_SCHEDULE_FILE");if(s){f=fopen(s,"r");if(!f)return 2;unsigned i;unsigned long long v;while(fscanf(f,"%u,%llx",&i,&v)==2){if(i>=1100)return 2;schedule[i]=v;}fclose(f);}
 events=fopen(argv[3],"w");fprintf(events,"index,frame,pc,state,div,elapsed,remaining,phase,lcd,lcdlong,timer\n");clock_t start=clock();Shadow7113Result r=shadow7113_run(&in,atoi(argv[4]));fclose(events);
 printf("{\"error\":%u,\"arm_pc\":\"%08X\",\"arm_op\":\"%08X\",\"guest_pc\":\"%04X\",\"frame\":%u,\"normal\":%u,\"final\":%u,\"reads\":%u,\"dv\":\"%04X\",\"shiny\":%u,\"dv_write_mask\":%u,\"dv_write_frame\":%u,\"instructions\":%llu,\"cpu_seconds\":%.6f}\n",r.error,r.arm_pc,r.arm_op,r.guest_pc,r.frame,r.normal,r.final,r.reads,r.dv,r.shiny,r.dv_write_mask,r.dv_write_frame,(unsigned long long)r.instructions,(double)(clock()-start)/CLOCKS_PER_SEC);return r.error?1:0;}
