/* Bounded neutral frame calibration. Only the main pause loop may release a
 * frame in response to return value 1. No RNG/DIV/DV/input memory is written. */
#include "mac7120_protocol.h"
#include <stdlib.h>
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
_Static_assert(sizeof(Mac7119Sample)==56,"Stable little-endian sample layout");
static Mac7119Sample *mac7119_samples;
static uint64_t mac7120_start;
static unsigned mac7122_static_changed;
static unsigned mac7120_late,mac7120_opcode,mac7120_log_hash,mac7120_log_bytes;
extern int snapshot7120_samples(const void*,uint32_t);
extern int host7120_arm(void);
static int mac7120_commit(const uint32_t*w){
 uint32_t a=0,s=suicune_native_pre_state(&a);
 if(!(s&0x80000000U)||a!=w[8]||(s&65535)!=w[9]||byte(0x22f766)!=255U||svcGetSystemTick()+10ULL*clock_hz>=mac7119_u64(w+23))return 0;
 advance=a;seed=s&65535;selected=w[22];models=1;committed=1;error=0;
 launch=mac7119_u64(w+23);resume=mac7119_u64(w+25);return 1;
}
static char mac7119_json[18000];
static void mac7119_exported(const Snapshot7116Meta*m,const uint32_t*h){mac7119_meta=*m;memcpy(mac7119_hashes,h,16);mac7119_have=1;}
unsigned gate7119_enabled(void){return mac7119_enabled_flag;}
unsigned gate7119_running(void){return mac7119_active;}
void gate7119_disable(void){mac7119_enabled_flag=mac7119_active=mac7119_inflight=0;free(mac7119_samples);mac7119_samples=NULL;}
static int mac7119_sample(Mac7119Sample*s){
 uint32_t rp=word(0x22f644),rawp=word(0x22f640),io=word(0x22f6d8)-128;
 if(!is_memory_mapped(rp)||!is_memory_mapped(rp+7)||!is_memory_mapped(rawp)||!is_memory_mapped(io+4))return 0;
 s->tick=svcGetSystemTick();s->state=suicune_native_pre_state(&s->advance);s->pc=word(0x22f5fc)&65535;
 s->native_keys=((uint32_t)byte(0x22f766)|((uint32_t)byte(0x22f767)<<8));s->rtc=wide(rp);s->raw=byte(rawp);s->div=byte(io+4);s->elapsed=word(0x22f604);s->remaining=word(0x22fa50);
 return (s->state&0x80000000U)&&(s->native_keys&255U)==255U;
}
static int mac7119_write_report(const char*phase,uint64_t after){
 int n=snprintf(mac7119_json,sizeof(mac7119_json),
 "{\"software\":7122,\"phase\":\"%s\",\"nonce\":\"%016llX\",\"requested_state_id\":\"%016llX\",\"before_state_id\":\"%016llX\",\"after_state_id\":\"%016llX\",\"requested_frames\":%u,\"completed_frames\":%u,\"minimum_cadence_fps\":%u,\"error\":%u,\"guest_input_sent\":false,\"encounter_launch_armed\":%s,\"opcode\":%u,\"static_snapshot_changed\":%s,\"absolute_start_tick\":%llu,\"late_tolerance_ticks\":%u,\"sample_count\":%u,\"sample_log_bytes\":%u,\"sample_log_fnv\":%u,\"samples\":[",
 phase,(unsigned long long)mac7119_nonce,(unsigned long long)mac7119_requested_id,(unsigned long long)mac7119_before.search_id,(unsigned long long)after,mac7119_frames,mac7119_done,mac7119_fps,mac7119_error,!strcmp(phase,"armed")?"true":"false",mac7120_opcode,mac7122_static_changed?"true":"false",(unsigned long long)mac7120_start,mac7120_late,mac7119_sample_count,mac7120_log_bytes,mac7120_log_hash);
 if(n<0||(unsigned)n>=sizeof(mac7119_json))return 0;
 for(unsigned i=0;i<mac7119_sample_count;i++){
  if(mac7119_sample_count>33 && i>0 && i+1<mac7119_sample_count)continue;
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
 mac7119_enabled_flag=1;mac7119_active=mac7119_inflight=0;mac7119_error=0;mac7119_poll_at=0;free(mac7119_samples);mac7119_samples=NULL;mac7119_sample_count=0;
 if(!snapshot7119_prepare()){mac7119_error=10;return 10;}return 0;
}
/* Called only at the paused bottom-screen boundary. */
unsigned gate7119_poll(uint32_t held){
 if(!mac7119_enabled_flag)return 0;
 uint64_t now=svcGetSystemTick();
 if(!mac7119_active){
  if(mac7119_error||held||now<mac7119_poll_at)return 0;
  mac7119_poll_at=now+clock_hz/4;uint32_t req[32];int read_ok=snapshot7119_request(req);
  if(read_ok<=0||memcmp(req,"S7120REQ",8)||req[31]!=mac7119_checksum(req,124))return 0;
  /* An already consumed request remains on SD; never execute it twice. */
  if(mac7119_u64(req+4)<=mac7119_last_nonce)return 0;
  mac7119_nonce=mac7119_u64(req+4);mac7119_requested_id=mac7119_u64(req+6);
  mac7119_frames=req[10];mac7119_fps=req[11];mac7119_done=mac7119_sample_count=0;
  memset(&mac7119_before,0,sizeof(mac7119_before));free(mac7119_samples);mac7119_samples=NULL;mac7120_opcode=req[18];mac7120_start=mac7119_u64(req+19);mac7120_late=req[21];mac7120_log_bytes=mac7120_log_hash=0;mac7122_static_changed=0;
  unsigned e=mac7119_validate(req,&mac7119_meta,mac7119_hashes,mac7119_last_nonce,now,held);
  if(e){mac7119_reject(20+e);return 0;}
  uint32_t adv=0,st=suicune_native_pre_state(&adv);
  if(!(st&0x80000000U)||adv!=mac7119_meta.advance||(st&65535)!=mac7119_meta.seed||byte(0x22f766)!=255U){mac7119_reject(27);return 0;}
  mac7119_nonce=mac7119_u64(req+4);mac7119_last_nonce=mac7119_nonce;mac7119_requested_id=mac7119_meta.search_id;
  mac7119_frames=req[10];mac7119_fps=req[11];mac7119_deadline=mac7119_u64(req+12);mac7119_done=mac7119_inflight=0;mac7119_error=0;
  mac7119_samples=calloc((size_t)mac7119_frames+1,sizeof(*mac7119_samples));if(!mac7119_samples){mac7119_reject(49);return 0;}
  /* Refresh the BEFORE image at acceptance, while still frozen. */
  snapshot7119_destination(1);uint32_t pid=0;e=gate7118_export(&pid);snapshot7119_destination(0);
  if(e){mac7119_reject(40+e);return 0;}
  mac7119_before=mac7119_meta;
  if(mac7120_opcode==1||mac7120_opcode==2){
   /* Calibration intentionally measures whether a prediction transfers to
    * hardware. Keep the actual BEFORE image even when native static RAM
    * changes while the guest is paused. Require the same code, entire heap,
    * ROM, ADV and seed; shiny reservations still require all four hashes. */
   mac7122_static_changed=req[15]!=mac7119_hashes[1];
   if(req[14]!=mac7119_hashes[0]||req[16]!=mac7119_hashes[2]||req[17]!=mac7119_hashes[3]||
      (mac7120_opcode==1&&mac7122_static_changed)||!mac7120_commit(req)){gate7113_cancel();mac7119_reject(80);return 0;}
   if(!mac7119_write_report("arm_prepared",0)){gate7113_cancel();mac7119_reject(81);return 0;}
   if(!host7120_arm()){gate7113_cancel();mac7119_reject(82);return 0;}
   if(svcGetSystemTick()+5ULL*clock_hz>=launch){gate7113_cancel();mac7119_reject(83);return 0;}
   if(!mac7119_write_report("armed",0)){gate7113_cancel();mac7119_reject(84);return 0;}
   mac7119_enabled_flag=0;free(mac7119_samples);mac7119_samples=NULL;return 0;
  }
  if(!mac7119_sample(&mac7119_samples[0])){mac7119_reject(50);return 0;}
  mac7119_sample_count=1;
  if(!mac7119_write_report("started",0)){mac7119_error=51;host7119_status(3,0,51);return 0;}
  mac7119_active=1;mac7119_next=mac7120_start;host7119_status(1,0,mac7119_frames);return 0;
 }
 if(mac7119_inflight){
  mac7119_inflight=0;mac7119_done++;
  if(!mac7119_sample(&mac7119_samples[mac7119_done]))mac7119_error=52;
  mac7119_sample_count=mac7119_done+1;
  if(mac7119_done<mac7119_frames&&mac7119_done%mac7119_fps==0)host7119_status(1,mac7119_done,mac7119_frames);
 }
 if(held)mac7119_error=53;
 if(now>=mac7119_deadline)mac7119_error=54;
 if(mac7119_error||mac7119_done==mac7119_frames){
  /* Stay paused while the user releases keys, then save the actual final state. */
  if(held){host7119_status(3,mac7119_done,mac7119_error);return 0;}
  mac7120_log_bytes=mac7119_sample_count*sizeof(*mac7119_samples);
  mac7120_log_hash=mac7119_checksum(mac7119_samples,mac7120_log_bytes);
  if(!snapshot7120_samples(mac7119_samples,mac7120_log_bytes))mac7119_error=71;
  uint32_t pid=0;unsigned e=gate7118_export(&pid);if(e)mac7119_error=60+e;
  uint64_t after=e?0:mac7119_meta.search_id;
  if(!mac7119_write_report(mac7119_error?"aborted":"complete",after))mac7119_error=70;
  mac7119_active=0;host7119_status(mac7119_error?3:2,mac7119_done,mac7119_error);return 0;
 }
 if(now<mac7119_next)return 0;
 if(now-mac7119_next>mac7120_late){mac7119_error=72;return 0;}
 /* This is the only path authorizing the caller to break for ONE frame. */
 uint64_t released=svcGetSystemTick();
 if(released-mac7119_next>mac7120_late){mac7119_error=72;return 0;}
 mac7119_samples[mac7119_done].release_tick=released;
 mac7119_inflight=1;mac7119_next=mac7120_start+(uint64_t)(mac7119_done+1)*clock_hz/mac7119_fps;return 1;
}
