/* Persist one complete INPUT to the private predictor. Never writes guest RAM.
 * The latest full check in a search replaces its previous snapshot; the header
 * identifies which CSV check it belongs to. Hashes + footer reject partial IO. */
#include "snapshot.h"
#include <string.h>
static uint32_t fnv(const uint8_t*p,uint32_t n){uint32_t h=2166136261U;for(uint32_t i=0;i<n;i++)h=(h^p[i])*16777619U;return h;}
static void wide(uint32_t*w,uint64_t v){w[0]=(uint32_t)v;w[1]=(uint32_t)(v>>32);}
int snapshot7116_emit(const Snapshot7116Meta*m,const uint8_t*code,const uint8_t*data,const uint8_t*rom,Snapshot7116Write put,void*opaque,uint32_t hashes[4]){
 if(!m||!code||!data||!rom||!put||!hashes||m->rom_size!=0x200000)return 0;
 uint32_t w[32]={0};memcpy(w,"S7116PRE",8);w[2]=1;w[3]=sizeof(w);wide(w+4,m->search_id);
 w[6]=m->check;w[7]=m->advance;w[8]=m->seed;w[9]=m->rom_base;w[10]=m->rom_size;w[11]=m->heap_base;w[12]=m->hz;
 wide(w+13,m->clock_ms);wide(w+15,m->clock_tick);wide(w+17,m->launch);wide(w+19,m->resume);
 hashes[0]=fnv(code,0xb1000);hashes[1]=fnv(data,0x14f000);hashes[2]=fnv(data+0x14f000,0x100000);hashes[3]=fnv(rom,m->rom_size);
 memcpy(w+21,hashes,16);w[25]=0xb1000;w[26]=0x14f000;w[27]=0x100000;w[28]=0x1b1000;w[29]=0x100000;w[31]=fnv((const uint8_t*)w,124);
 return put(opaque,w,sizeof(w))&&put(opaque,code,0xb1000)&&put(opaque,data,0x24f000)&&put(opaque,"DONE7116",8);
}
#ifdef __3DS__
#include <3ds.h>
#include <stdio.h>
typedef struct{Handle file;uint64_t offset;} Writer;
static int sd_put(void*o,const void*b,uint32_t n){Writer*w=o;const uint8_t*p=b;for(uint32_t off=0;off<n;){uint32_t take=n-off,written=0;if(take>16384)take=16384;Result e=FSFILE_Write(w->file,&written,w->offset,p+off,take,0);if(R_FAILED(e)||written!=take)return 0;off+=take;w->offset+=take;}return 1;}
int snapshot7116_save(const Snapshot7116Meta*m,const uint8_t*code,const uint8_t*data,const uint8_t*rom,uint32_t hashes[4]){
 if(R_FAILED(fsInit()))return 0;FS_Archive sd;
 if(R_FAILED(FSUSER_OpenArchive(&sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){fsExit();return 0;}
 FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/traces"),0);
 char path[160];snprintf(path,sizeof(path),"/luma/plugins/pokereader/traces/shiny7116_pre_%016llX.bin",(unsigned long long)m->search_id);
 Writer w={0,0};Result e=FSUSER_OpenFile(&w.file,sd,fsMakePath(PATH_ASCII,path),FS_OPEN_WRITE|FS_OPEN_CREATE,0);FSUSER_CloseArchive(sd);
 if(R_FAILED(e)){fsExit();return 0;}
 int ok=!R_FAILED(FSFILE_SetSize(w.file,0))&&snapshot7116_emit(m,code,data,rom,sd_put,&w,hashes);
 Result flush=FSFILE_Flush(w.file),close=FSFILE_Close(w.file);fsExit();return ok&&!R_FAILED(flush)&&!R_FAILED(close);
}
#endif
