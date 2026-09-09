#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint64_t mac7119_nonce=100,mac7119_requested_id=1234,launch=10000000000ULL,resume=11300000000ULL,now=1000;
static uint32_t advance=507,selected=0xb2fe;
static unsigned writes,fail;
static char saved[1536],path_saved[128];
uint64_t svcGetSystemTick(void){return now;}
static int append_file(const char*p,const char*s,int fresh){writes++;assert(fresh);strcpy(saved,s);strcpy(path_saved,p);return !fail;}
#include "runtime.inc"
int main(void){
 gate7123_begin();assert(!writes);
 gate7123_note(2,launch,64,0);gate7123_note(3,launch+100,64,0);gate7123_note(4,launch+200,0,0);gate7123_note(5,resume,0,0);assert(!writes);
 assert(gate7123_finish(20,resume+900,0,0x1b2fe));assert(writes==1);assert(strstr(saved,"predicted_dv,B2FE")&&strstr(saved,"20,11300000900,0,111358"));
 char prior[1536];strcpy(prior,saved);gate7123_note(2,0,0,0);assert(gate7123_finish(15,0,0,0));assert(writes==1&&!strcmp(prior,saved));
 for(unsigned reason=10;reason<=15;reason++){
  mac7119_nonce++;gate7123_begin();unsigned count=writes;assert(gate7123_finish(reason,launch+2681119,0,7));assert(writes==count+1);assert(events7123.rows[1].kind==reason);assert(events7123.count==2);
 }
 assert(strstr(path_saved,"mac7123_000000000000006A.csv"));
 mac7119_nonce++;gate7123_begin();for(unsigned i=0;i<40;i++)gate7123_note(2+i%2,i,0,0);assert(events7123.count==16);assert(gate7123_finish(10,555,8,0));assert(events7123.rows[15].kind==10&&events7123.rows[15].tick==555);
 char small[8];assert(!events7123_render(&events7123,small,sizeof(small)));
 mac7119_nonce++;gate7123_begin();fail=1;assert(!gate7123_finish(12,100,0,0));assert(events7123.finished);
 puts("PASS: no SD IO at launch/release/resume; terminal reasons, DV, overflow and failure are retained; later cancellation cannot overwrite result");
}
