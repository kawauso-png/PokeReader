#ifndef MAC7120_PROTOCOL_H
#define MAC7120_PROTOCOL_H
#include <stdint.h>
#include <string.h>
#include "snapshot.h"
static uint32_t mac7119_checksum(const void *data,uint32_t n){const uint8_t*p=data;uint32_t h=2166136261U;for(uint32_t i=0;i<n;i++)h=(h^p[i])*16777619U;return h;}
static uint64_t mac7119_u64(const uint32_t*w){return (uint64_t)w[0]|(uint64_t)w[1]<<32;}
/* Opcode0: bounded absolute-grid neutral frames; opcode1: physical-UP candidate arm. */
static unsigned mac7119_validate(const uint32_t*w,const Snapshot7116Meta*m,const uint32_t hashes[4],uint64_t last,uint64_t now,uint32_t held){
 if(memcmp(w,"S7120REQ",8)||w[2]!=2||w[3]!=128||w[31]!=mac7119_checksum(w,124))return 1;
 if(w[18]>1 || (w[11]!=30&&w[11]!=60))return 2;
 for(unsigned i=27;i<31;i++)if(w[i])return 2;
 if(w[18]==0){
  if(w[10]<1||w[10]>65535||w[22]||w[23]||w[24]||w[25]||w[26])return 2;
  uint64_t start=mac7119_u64(w+19),end=mac7119_u64(w+12);
  if(start<=now||start-now>3600ULL*m->hz||w[21]<m->hz/1000||w[21]>m->hz/200)return 5;
  if(end<=start+(uint64_t)w[10]*m->hz/w[11]+m->hz)return 5;
 }else{
  if(w[10]||w[19]||w[20]||w[21]||w[22]>65535||(w[22]&0xfff)!=0xaaa||!(w[22]&0x2000))return 2;
  uint64_t launch=mac7119_u64(w+23),resume=mac7119_u64(w+25);
  if(launch<=now+10ULL*m->hz||launch-now>3600ULL*m->hz||resume<launch+5ULL*m->hz||resume>launch+6ULL*m->hz||resume%4481233ULL||(resume/4481233ULL)%16!=14||mac7119_u64(w+12)<=resume+m->hz)return 5;
 }
 if(mac7119_u64(w+6)!=m->search_id||w[8]!=m->advance||w[9]!=m->seed||memcmp(w+14,hashes,16))return 3;
 if(!mac7119_u64(w+4)||mac7119_u64(w+4)<=last)return 4;
 uint64_t end=mac7119_u64(w+12);if(end<=now||end-now>7200ULL*m->hz)return 5;
 if(held)return 6;
 return 0;
}
#endif
