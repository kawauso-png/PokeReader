#ifndef DV_ENDPOINT_7115_H
#define DV_ENDPOINT_7115_H
#include <stdint.h>
/* Observe the two actual enemy-DV stores in the supported Japanese VC ROM.
 * PC points past the fetched GB opcode: LD [HLI],A at 69BB, LD [HL],C at 69BC.
 * This only records private replay writes; it never changes guest memory. */
typedef struct { uint32_t base,frame; uint16_t dv; uint8_t mask; } DvEndpoint7115;
static inline void dv7115_observe(DvEndpoint7115 *e,uint32_t base,uint32_t addr,
                                 unsigned n,uint32_t value,unsigned pc,unsigned bank,unsigned frame){
 if(n!=1||bank!=15)return;
 if(addr==base+0x23d&&pc==0x69bc){
  e->base=base;e->dv=(value&255)<<8;e->mask=1;e->frame=frame;
 }else if(addr==base+0x23e&&pc==0x69bd&&e->mask==1&&e->base==base){
  e->dv|=value&255;e->mask=3;e->frame=frame;
 }
}
#endif
