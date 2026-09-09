/* Bounded neutral frame calibration. Only the main pause loop may release a
 * frame in response to return value 1. No RNG/DIV/DV/input memory is written. */
#include "mac7119_protocol.h"
extern int snapshot7119_request(uint32_t*);
extern int snapshot7119_prepare(void);
extern int snapshot7119_report(const char*,uint32_t);
extern void snapshot7119_destination(unsigned);
extern void host7119_status(unsigned,unsigned,unsigned);
typedef struct {uint64_t tick,rtc,release_tick;uint32_t advance,state,pc,native_keys,raw,div,elapsed,remaining;} Mac7119Sample;
static Snapshot7116Meta mac7119_meta,mac7119_before;
static uint32_t mac7119_hashes[4],mac7119_have,mac7119_enabled_flag;
static uint64_t mac7119_last_nonce,mac7119_nonce,mac7119_requested_id,mac7119_next,mac7119_deadline,mac7119_poll_at;
static unsigned mac7119_active,mac7119_inflight,mac7119_frames,mac7119_done,mac7119_fps,mac7119_error,mac7119_sample_count;
static Mac7119Sample mac7119_samples[33];
static char mac7119_json[18000];
static void mac7119_exported(const Snapshot7116Meta*m,const uint32_t*h){mac7119_meta=*m;memcpy(mac7119_hashes,h,16);mac7119_have=1;}
unsigned gate7119_enabled(void){return mac7119_enabled_flag;}
unsigned gate7119_running(void){return mac7119_active;}
void gate7119_disable(void){mac7119_enabled_flag=mac7119_active=mac7119_inflight=0;}
static int mac7119_sample(Mac7119Sample*s){
 uint32_t rp=word(0x22f644),rawp=word(0x22f640),io=word(0x22f6d8)-128;
 if(!is_memory_mapped(rp)||!is_memory_mapped(rp+7)||!is_memory_mapped(rawp)||!is_memory_mapped(io+4))return 0;
 s->tick=svcGetSystemTick();s->state=suicune_native_pre_state(&s->advance);s->pc=word(0x22f5fc)&65535;
 s->native_keys=word(0x22f766)&65535;s->rtc=wide(rp);s->raw=byte(rawp);s->div=byte(io+4);s->elapsed=word(0x22f604);s->remaining=word(0x22fa50);
 return (s->state&0x80000000U)&&s->native_keys==0xffffU;
}
static int mac7119_write_report(const char*phase,uint64_t after){
 int n=snprintf(mac7119_json,sizeof(mac7119_json),
 "{\"software\":7119,\"phase\":\"%s\",\"nonce\":\"%016llX\",\"requested_state_id\":\"%016llX\",\"before_state_id\":\"%016llX\",\"after_state_id\":\"%016llX\",\"requested_frames\":%u,\"completed_frames\":%u,\"minimum_cadence_fps\":%u,\"error\":%u,\"guest_input_sent\":false,\"encounter_launch_armed\":false,\"samples\":[",
 phase,(unsigned long long)mac7119_nonce,(unsigned long long)mac7119_requested_id,(unsigned long long)mac7119_before.search_id,(unsigned long long)after,mac7119_frames,mac7119_done,mac7119_fps,mac7119_error);
 if(n<0||(unsigned)n>=sizeof(mac7119_json))return 0;
 for(unsigned i=0;i<mac7119_sample_count;i++){
  Mac7119Sample*s=&mac7119_samples[i];int k=snprintf(mac7119_json+n,sizeof(mac7119_json)-n,
   "%s{\"index\":%u,\"tick\":%llu,\"release_tick\":%llu,\"advance\":%lu,\"state\":%lu,\"pc\":%lu,\"native_keys\":%lu,\"rtc_packed\":%llu,\"rtc_raw\":%lu,\"div\":%lu,\"elapsed\":%lu,\"remaining\":%lu}",i?",":"",i,(unsigned long long)s->tick,(unsigned long long)s->release_tick,(unsigned long)s->advance,(unsigned long)s->state,(unsigned long)s->pc,(unsigned long)s->native_keys,(unsigned long long)s->rtc,(unsigned long)s->raw,(unsigned long)s->div,(unsigned long)s->elapsed,(unsigned long)s->remaining);
  if(k<0||(unsigned)k>=sizeof(mac7119_json)-(unsigned)n)return 0;n+=k;
 }
 if((unsigned)n+4>=sizeof(mac7119_json))return 0;memcpy(mac7119_json+n,"]}\n",3);n+=3;
 return snapshot7119_report(mac7119_json,(uint32_t)n);
}
static void mac7119_reject(unsigned error){
 mac7119_error=error;mac7119_write_report("rejected",0);host7119_status(3,0,error);
}
unsigned gate7119_enable(void){
 if(!mac7119_have)return 9;
 mac7119_enabled_flag=1;mac7119_active=mac7119_inflight=0;mac7119_error=0;mac7119_poll_at=0;
 if(!snapshot7119_prepare()){mac7119_error=10;return 10;}return 0;
}
/* Called only at the paused bottom-screen boundary. */
unsigned gate7119_poll(uint32_t held){
 if(!mac7119_enabled_flag)return 0;
 uint64_t now=svcGetSystemTick();
 if(!mac7119_active){
  if(mac7119_error||held||now<mac7119_poll_at)return 0;
  mac7119_poll_at=now+clock_hz/4;uint32_t req[32];int read_ok=snapshot7119_request(req);
  if(read_ok<=0||memcmp(req,"S7119REQ",8)||req[31]!=mac7119_checksum(req,124))return 0;
  /* An already consumed request remains on SD; never execute it twice. */
  if(mac7119_u64(req+4)<=mac7119_last_nonce)return 0;
  mac7119_nonce=mac7119_u64(req+4);mac7119_requested_id=mac7119_u64(req+6);
  mac7119_frames=req[10];mac7119_fps=req[11];mac7119_done=mac7119_sample_count=0;
  memset(&mac7119_before,0,sizeof(mac7119_before));memset(mac7119_samples,0,sizeof(mac7119_samples));
  unsigned e=mac7119_validate(req,&mac7119_meta,mac7119_hashes,mac7119_last_nonce,now,held);
  if(e){mac7119_reject(20+e);return 0;}
  uint32_t adv=0,st=suicune_native_pre_state(&adv);
  if(!(st&0x80000000U)||adv!=mac7119_meta.advance||(st&65535)!=mac7119_meta.seed||(word(0x22f766)&65535)!=0xffffU){mac7119_reject(27);return 0;}
  mac7119_nonce=mac7119_u64(req+4);mac7119_last_nonce=mac7119_nonce;mac7119_requested_id=mac7119_meta.search_id;
  mac7119_frames=req[10];mac7119_fps=req[11];mac7119_deadline=mac7119_u64(req+12);mac7119_done=mac7119_inflight=0;mac7119_error=0;
  memset(mac7119_samples,0,sizeof(mac7119_samples));
  /* Refresh the BEFORE image at acceptance, while still frozen. */
  snapshot7119_destination(1);uint32_t pid=0;e=gate7118_export(&pid);snapshot7119_destination(0);
  if(e){mac7119_reject(40+e);return 0;}
  mac7119_before=mac7119_meta;
  if(!mac7119_sample(&mac7119_samples[0])){mac7119_reject(50);return 0;}
  mac7119_sample_count=1;
  if(!mac7119_write_report("started",0)){mac7119_error=51;host7119_status(3,0,51);return 0;}
  mac7119_active=1;mac7119_next=svcGetSystemTick()+clock_hz/mac7119_fps;host7119_status(1,0,mac7119_frames);return 0;
 }
 if(mac7119_inflight){
  mac7119_inflight=0;mac7119_done++;
  if(!mac7119_sample(&mac7119_samples[mac7119_done]))mac7119_error=52;
  mac7119_sample_count=mac7119_done+1;
 }
 if(held)mac7119_error=53;
 if(now>=mac7119_deadline)mac7119_error=54;
 if(mac7119_error||mac7119_done==mac7119_frames){
  /* Stay paused while the user releases keys, then save the actual final state. */
  if(held){host7119_status(3,mac7119_done,mac7119_error);return 0;}
  uint32_t pid=0;unsigned e=gate7118_export(&pid);if(e)mac7119_error=60+e;
  uint64_t after=e?0:mac7119_meta.search_id;
  if(!mac7119_write_report(mac7119_error?"aborted":"complete",after))mac7119_error=70;
  mac7119_active=0;host7119_status(mac7119_error?3:2,mac7119_done,mac7119_error);return 0;
 }
 if(now<mac7119_next)return 0;
 /* This is the only path authorizing the caller to break for ONE frame. */
 mac7119_samples[mac7119_done].release_tick=svcGetSystemTick();
 mac7119_inflight=1;mac7119_next=now+clock_hz/mac7119_fps;return 1;
}
