#ifndef MAC7119_PROTOCOL_H
#define MAC7119_PROTOCOL_H
#include <stdint.h>
#include <string.h>
#include "snapshot.h"
static uint32_t mac7119_checksum(const void *data,uint32_t n){const uint8_t*p=data;uint32_t h=2166136261U;for(uint32_t i=0;i<n;i++)h=(h^p[i])*16777619U;return h;}
static uint64_t mac7119_u64(const uint32_t*w){return (uint64_t)w[0]|(uint64_t)w[1]<<32;}
/* Only a bounded, input-neutral step request exists in this protocol. */
static unsigned mac7119_validate(const uint32_t*w,const Snapshot7116Meta*m,const uint32_t hashes[4],uint64_t last,uint64_t now,uint32_t held){
 if(memcmp(w,"S7119REQ",8)||w[2]!=1||w[3]!=128||w[31]!=mac7119_checksum(w,124))return 1;
 if(w[10]<1||w[10]>32||(w[11]!=30&&w[11]!=60))return 2;
 for(unsigned i=18;i<31;i++)if(w[i])return 2;
 if(mac7119_u64(w+6)!=m->search_id||w[8]!=m->advance||w[9]!=m->seed||memcmp(w+14,hashes,16))return 3;
 if(!mac7119_u64(w+4)||mac7119_u64(w+4)<=last)return 4;
 uint64_t end=mac7119_u64(w+12);if(end<=now||end-now>1800ULL*m->hz)return 5;
 if(held)return 6;
 return 0;
}
#endif
