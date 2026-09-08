/* Called ONLY from the frozen host pause loop or final trace save. */
#include <3ds.h>
#include <stdio.h>
#include <string.h>
#include "pnp.h"
#include "rank_core.h"
#include "rank_runtime.h"
extern uint32_t suicune_rank_pre_state(uint32_t *advance);
extern uint32_t host_trace_file_write(const char*,uint32_t);
static uint8_t ram[8192],io[256];
static uint32_t error_code,checks,cycles,pre_advance,seed,candidates,rom_seen,rom_hash,pre_hash;
static uint64_t pre_id,search_id;
static int committed,valid,scored;
static int rom_dump_ok;
#define RANK_LIMIT 128U
static int mapped(uint32_t ptr,uint32_t length) {
    if(!ptr||!length||ptr>UINT32_MAX-(length-1))return 0;
    uint32_t last=ptr+length-1;
    if(!is_memory_mapped(ptr)||!is_memory_mapped(last))return 0;
    for(uint32_t p=(ptr&~4095U)+4096U;p<=last;p+=4096U)if(!is_memory_mapped(p))return 0;
    return 1;
}
static uint32_t word_at(uint32_t addr){return *(const volatile uint32_t*)addr;}
static uint32_t fnv(const uint8_t *data,uint32_t n,uint32_t h){for(uint32_t i=0;i<n;i++)h=(h^data[i])*16777619U;return h;}
void rank7108_begin(void){error_code=checks=cycles=committed=valid=scored=0;rom_dump_ok=0;pre_id=0;pre_advance=seed=pre_hash=0;search_id=svcGetSystemTick();}
/* Diagnostic export only. The game's loaded ROM is read, never modified.
   Do not accept a different ROM merely because the observed hash is stable. */
static int save_diag_file(FS_Archive sd,const char *name,const uint8_t *data,uint32_t length) {
    Handle file;uint64_t size=0;
    if(R_FAILED(FSUSER_OpenFile(&file,sd,fsMakePath(PATH_ASCII,name),FS_OPEN_WRITE|FS_OPEN_CREATE,0)))return 0;
    int ok=!R_FAILED(FSFILE_GetSize(file,&size)) && size==0;
    for(uint32_t offset=0;ok && offset<length;) {
        uint32_t count=length-offset,written=0;if(count>16384)count=16384;
        Result r=FSFILE_Write(file,&written,offset,data+offset,count,0);
        if(R_FAILED(r)||written!=count){ok=0;break;}offset+=count;
    }
    Result flush=FSFILE_Flush(file),close=FSFILE_Close(file);
    return ok && !R_FAILED(flush) && !R_FAILED(close);
}
static void dump_rom(uint32_t rom) {
    if(R_FAILED(fsInit()))return;
    FS_Archive sd;
    if(R_FAILED(FSUSER_OpenArchive(&sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){fsExit();return;}
    FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader"),0);
    FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/traces"),0);
    char name[160],info[384];
    snprintf(name,sizeof(name),"/luma/plugins/pokereader/traces/rank7108_rom_%016llX.bin",(unsigned long long)search_id);
    int saved=save_diag_file(sd,name,(const uint8_t*)rom,2097152);
    snprintf(info,sizeof(info),"version=S7108D\nsearch_id=%016llX\nrom_pointer=%08X\nlength=2097152\nexpected_fnv=6C177283\nobserved_fnv=%08X\nbinary_saved=%d\n",
        (unsigned long long)search_id,(unsigned)rom,(unsigned)rom_hash,saved);
    snprintf(name,sizeof(name),"/luma/plugins/pokereader/traces/rank7108_rom_%016llX.txt",(unsigned long long)search_id);
    int meta=save_diag_file(sd,name,(const uint8_t*)info,strlen(info));
    rom_dump_ok=saved && meta;FSUSER_CloseArchive(sd);fsExit();
}
int rank7108_rom_dump_ok(void){return rom_dump_ok;}
int rank7108_rom_preflight(void) {
    error_code=0;rom_dump_ok=0;
    if(!mapped(0x22f6c4,4)){error_code=2;return 0;}
    uint32_t rom=word_at(0x22f6c4);
    if(!mapped(rom,2097152)){error_code=4;return 0;}
    rom_hash=fnv((const uint8_t*)rom,2097152,2166136261U);
    if(rom_hash!=0x6c177283U){rom_seen=0;error_code=5;dump_rom(rom);return 0;}
    rom_seen=rom;return 1;
}
uint32_t rank7108_error(void){return error_code;}
uint32_t rank7108_checks(void){return checks;}
uint32_t rank7108_cycles(void){return cycles;}
int rank7108_evaluate(void) {
    valid=committed=scored=0;error_code=0;cycles=0;candidates=0;checks++;
    uint32_t st=suicune_rank_pre_state(&pre_advance);
    if(!(st&0x80000000U)){error_code=1;return -1;}
    seed=st&65535U;
    if(!mapped(0x0022f6c4,0xd4)){error_code=2;return -1;}
    uint32_t rom=word_at(0x22f6c4),wram=word_at(0x22f6c8),bank=word_at(0x22f768);
    uint32_t hram=word_at(0x22f6d8),div=word_at(0x22f794);
    if(hram<0x80 || div!=hram-0x7c || !mapped(wram,4096)||!mapped(bank,4096)||!mapped(hram-0x80,256)) {error_code=3;return -1;}
    if(rom!=rom_seen) {
        if(!mapped(rom,2097152)){error_code=4;return -1;}
        rom_hash=fnv((const uint8_t*)rom,2097152,2166136261U);
        if(rom_hash!=0x6c177283U){error_code=5;return -1;}
        rom_seen=rom;
    }
    memcpy(ram,(const void*)wram,4096);memcpy(ram+4096,(const void*)bank,4096);
    memcpy(io,(const void*)(hram-0x80),256);
    if((((uint32_t)io[0xe1]<<8)|io[0xe2])!=seed){error_code=6;return -1;}
    pre_hash=fnv(io,256,fnv(ram,8192,2166136261U));
    uint32_t e=rank7108_audio((const uint8_t*)rom,2097152,ram,io,&cycles,NULL);
    if(e){error_code=0x100U+e;return -1;}
    /* No extrapolation past the workload range present in this model. */
    if(cycles<8569||cycles>11350)return 0;
    candidates=rank7108_score(seed,(int)cycles,-1);
    scored=1;
    valid=rank7108_best_rank()>0 && rank7108_best_rank()<=RANK_LIMIT && rank7108_support()>=2;
    return valid;
}
typedef struct {Handle file;uint64_t offset;int ok;} Writer;
static void put(Writer *w,const char *s) {
    if(!w->ok)return;
    uint32_t n=(uint32_t)strlen(s),written=0;
    Result r=FSFILE_Write(w->file,&written,w->offset,s,n,0);
    if(R_FAILED(r)||written!=n){w->ok=0;error_code=0x201;return;}
    w->offset+=written;
}
static void pre_header(char *line,size_t len) {
    snprintf(line,len,"RANK7108_PRE,%016llX,%s,%u,%04X,%u,2A35,2A40,0000,128,%04X,%u,%u,%u,%u,%08X,%08X\n",
        (unsigned long long)pre_id,rank7108_model_id(),(unsigned)pre_advance,(unsigned)seed,(unsigned)cycles,
        rank7108_best_shiny(),(unsigned)rank7108_best_rank(),(unsigned)rank7108_support(),(unsigned)candidates,
        (unsigned)checks,(unsigned)pre_hash,(unsigned)rom_hash);
}
int rank7108_log_scan(int decision) {
    /* One row per inspected PRE, including rejections. Lets the next analysis
       measure which RNG/audio combinations actually occur without more UPs. */
    uint32_t original_error=error_code;
    if(R_FAILED(fsInit())){error_code=0x210;return 0;}
    FS_Archive sd;
    if(R_FAILED(FSUSER_OpenArchive(&sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){error_code=0x211;fsExit();return 0;}
    FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader"),0);
    FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/traces"),0);
    char name[128];snprintf(name,sizeof(name),"/luma/plugins/pokereader/traces/rank7108_scan_%016llX.csv",(unsigned long long)search_id);
    Writer w={0,0,1};uint64_t size=0;
    Result r=FSUSER_OpenFile(&w.file,sd,fsMakePath(PATH_ASCII,name),FS_OPEN_WRITE|FS_OPEN_CREATE,0);
    FSUSER_CloseArchive(sd);
    if(R_FAILED(r)){error_code=0x212;fsExit();return 0;}
    if(R_FAILED(FSFILE_GetSize(w.file,&size))||(checks==1 && size!=0)||(checks>1 && size==0)) {
        error_code=0x213;FSFILE_Close(w.file);fsExit();return 0;
    }
    w.offset=size;
    if(!size)put(&w,"record,search_id,model,check,advance,seed,audio_cycles,decision,error,candidates,shiny_dv,shiny_rank,support,pre_hash,rom_fnv\n");
    char line[384];snprintf(line,sizeof(line),"RANK7108_SCAN,%016llX,%s,%u,%u,%04X,%u,%d,%08X,%u,%04X,%u,%u,%08X,%08X\n",
        (unsigned long long)search_id,rank7108_model_id(),(unsigned)checks,(unsigned)pre_advance,(unsigned)seed,(unsigned)cycles,
        decision,(unsigned)original_error,(unsigned)candidates,scored?rank7108_best_shiny():0,
        (unsigned)(scored?rank7108_best_rank():0),(unsigned)(scored?rank7108_support():0),(unsigned)pre_hash,(unsigned)rom_hash);
    put(&w,line);
    Result flush=FSFILE_Flush(w.file),close=FSFILE_Close(w.file);fsExit();
    if(!w.ok||R_FAILED(flush)||R_FAILED(close)){error_code=0x214;return 0;}
    return 1;
}
int rank7108_commit(void) {
    uint32_t now=0,st=suicune_rank_pre_state(&now);
    if(!valid||!(st&0x80000000U)||now!=pre_advance||(st&65535U)!=seed){error_code=7;return 0;}
    pre_id=svcGetSystemTick();committed=0;
    if(R_FAILED(fsInit())){error_code=0x202;return 0;}
    FS_Archive sd;
    if(R_FAILED(FSUSER_OpenArchive(&sd,ARCHIVE_SDMC,fsMakePath(PATH_EMPTY,"")))){error_code=0x203;fsExit();return 0;}
    FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader"),0);
    FSUSER_CreateDirectory(sd,fsMakePath(PATH_ASCII,"/luma/plugins/pokereader/traces"),0);
    char name[128];snprintf(name,sizeof(name),"/luma/plugins/pokereader/traces/rank7108_%016llX.csv",(unsigned long long)pre_id);
    Writer w={0,0,1};uint64_t size=0;
    Result opened=FSUSER_OpenFile(&w.file,sd,fsMakePath(PATH_ASCII,name),FS_OPEN_WRITE|FS_OPEN_CREATE,0);
    FSUSER_CloseArchive(sd);
    if(R_FAILED(opened)){error_code=0x204;fsExit();return 0;}
    if(R_FAILED(FSFILE_GetSize(w.file,&size))||size!=0){error_code=0x205;FSFILE_Close(w.file);fsExit();return 0;}
    char line[384];
    put(&w,"# EXPERIMENTAL RANKING; score and rank are not shiny success probabilities\n");
    put(&w,"record,id,model,advance,seed,audio_cycles,ap,sp,keys,rank_limit,shiny_dv,shiny_rank,support,candidates,checks,pre_hash,rom_fnv\n");
    pre_header(line,sizeof(line));put(&w,line);
    put(&w,"record,ordinal,dv,weight\n");
    for(unsigned i=0;i<candidates && i<512;i++) {
        uint16_t dv=rank7108_top(i);snprintf(line,sizeof(line),"RANK7108_TOP,%u,%04X,%.17g\n",i+1,dv,rank7108_weight(dv));put(&w,line);
    }
    Result flush=FSFILE_Flush(w.file),close=FSFILE_Close(w.file);fsExit();
    if(!w.ok||R_FAILED(flush)||R_FAILED(close)){if(!error_code)error_code=0x206;return 0;}
    committed=1;return 1;
}
void rank7108_append_result(uint32_t advance,uint32_t present,uint32_t dv) {
    if(!committed)return;
    char line[384];pre_header(line,sizeof(line));host_trace_file_write(line,strlen(line));
    uint32_t match=advance==pre_advance;
    snprintf(line,sizeof(line),"RANK7108_RESULT,%016llX,%u,%u,%04X,%u\n",(unsigned long long)pre_id,
        (unsigned)match,(unsigned)present,(unsigned)(dv&65535U),(unsigned)(match&&present?rank7108_rank(dv):0));
    host_trace_file_write(line,strlen(line));
}
