"""Exercise the production diagnostic functions with host filesystem/memory mocks."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent.parent
runtime = (root / 'v7108/rank_runtime.c').read_text()
block = runtime[runtime.index('static int save_diag_file('):runtime.index('uint32_t rank7108_error(')]
# Only translate the 32-bit device pointer into the host mock's byte array.
block = block.replace('(const uint8_t*)rom', 'rom_bytes(rom)')
harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int Handle;typedef int Result;typedef int FS_Archive;
#define R_FAILED(x) ((x)<0)
#define PATH_ASCII 1
#define PATH_EMPTY 0
#define FS_OPEN_WRITE 1
#define FS_OPEN_CREATE 2
#define ARCHIVE_SDMC 1
static uint32_t error_code,rom_seen,rom_hash;
static uint64_t search_id=1;
static int rom_dump_ok,fail,opened,closed,exited,archive_closed,write_count,good_hash,map_ok;
static uint8_t original[2097152],out[2097152];
static char meta[384];
static uint32_t lengths[3];
static const uint8_t *rom_bytes(uint32_t p){assert(p==0x08800010);return original;}
static int mapped(uint32_t p,uint32_t n){return map_ok;}
static uint32_t word_at(uint32_t p){assert(p==0x22f6c4);return 0x08800010;}
static uint32_t fnv(const uint8_t *p,uint32_t n,uint32_t h){assert(p==original && n==2097152);return good_hash?0x6c177283:0x57d31952;}
static int fsInit(void){return fail==1?-1:0;}
static void fsExit(void){exited++;}
static const char *fsMakePath(int t,const char *s){return s;}
static int FSUSER_OpenArchive(FS_Archive *a,int t,const char*p){*a=1;return fail==2?-1:0;}
static void FSUSER_CloseArchive(FS_Archive a){archive_closed++;}
static int FSUSER_CreateDirectory(FS_Archive a,const char*p,int n){return 0;}
static int FSUSER_OpenFile(Handle*f,FS_Archive a,const char*p,int flags,int attr){
    if(fail==3)return -1;
    *f=strstr(p,".bin")?1:2;opened++;return 0;
}
static int FSFILE_GetSize(Handle f,uint64_t*s){*s=fail==4?123:0;return fail==5?-1:0;}
static int FSFILE_Write(Handle f,uint32_t*w,uint64_t off,const void*p,uint32_t n,int flags){
    assert(n<=16384);write_count++;*w=fail==6?n-1:n;
    if(fail==7)return -1;
    if(f==1){assert(off+n<=sizeof(out));memcpy(out+off,p,n);}
    else{assert(off+n<sizeof(meta));memcpy(meta+off,p,n);}
    lengths[f]+=*w;return 0;
}
static int FSFILE_Flush(Handle f){return fail==8?-1:0;}
static int FSFILE_Close(Handle f){closed++;return fail==9?-1:0;}
BLOCK
static void init(void){
    fail=opened=closed=exited=archive_closed=write_count=good_hash=rom_dump_ok=0;
    error_code=0;rom_seen=0;map_ok=1;memset(lengths,0,sizeof(lengths));memset(meta,0,sizeof(meta));
    for(unsigned i=0;i<sizeof(original);i++)original[i]=(uint8_t)(i*17+31);
}
int main(void){
    init();assert(!rank7108_rom_preflight());assert(error_code==5 && rom_dump_ok && !rom_seen);
    assert(lengths[1]==2097152 && !memcmp(original,out,sizeof(original)));
    assert(strstr(meta,"observed_fnv=57D31952") && strstr(meta,"binary_saved=1"));
    assert(opened==2 && closed==2 && exited==1 && archive_closed==1);
    for(int f=1;f<=9;f++){
        init();fail=f;assert(!rank7108_rom_preflight());assert(error_code==5 && !rom_dump_ok && !rom_seen);
        assert(opened==closed);for(unsigned i=0;i<sizeof(original);i++)assert(original[i]==(uint8_t)(i*17+31));
    }
    init();good_hash=1;assert(rank7108_rom_preflight());assert(!error_code && rom_seen==0x08800010 && !opened);
    init();map_ok=0;assert(!rank7108_rom_preflight());assert(error_code==2 && !opened);
    puts("PASS: ROM diagnostic writes exact 2 MiB; mismatch never passes; short writes, collisions and I/O failures cannot report success");
}
'''.replace('BLOCK', block)
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td)
    (tmp / 'test.c').write_text(harness)
    subprocess.run(['cc', '-std=c99', '-O2', str(tmp / 'test.c'), '-o', str(tmp / 'test')], check=True)
    subprocess.run([str(tmp / 'test')], check=True)

c = (root / '3gx/sources/main.c').read_text()
start = c.index('// Ranked experiment: auto-check frozen PRE candidates before UP.')
end = c.index('if (false && (just_pressed & KEY_DUP))', start)
flow = c[start:end]
assert flow.index('rank7108_rom_preflight()') < flow.index('rank7108_hunting=true;') < flow.index('search_suicune_practical_targets();')
failure = flow[flow.index('if(!rank7108_rom_preflight())'):flow.index('rank7108_hunting=true;')]
assert 'continue;' in failure and 'arm_suicune' not in failure and 'break;' not in failure
assert 'ROM DUMP SAVED - RETURN SD' in failure
print('PASS: diagnostic failure stays paused before root search or physical-UP arming')
