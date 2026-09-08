#ifndef SHADOW7113_H
#define SHADOW7113_H
#include <stdint.h>
#include "arm_core.h"
typedef struct {
 const uint8_t *code,*rom;uint32_t rom_base,rom_size,heap_base;
 uint8_t *static_data,*heap_data;
 uint64_t (*rtc)(unsigned frame,void*);void*opaque;
 void (*event)(unsigned frame,unsigned pc,unsigned state,unsigned div,unsigned elapsed,unsigned remaining,unsigned lcd,unsigned lcdlong,unsigned timer,void*);
 int (*progress)(unsigned frame,uint64_t instructions,void*);
} Shadow7113Input;
typedef struct {uint32_t error,arm_pc,arm_op,guest_pc,frame,normal,final,reads,lcd,lcdlong,timer;uint64_t instructions;uint16_t dv;uint8_t shiny;uint32_t dv_write_mask,dv_write_frame;} Shadow7113Result;
Shadow7113Result shadow7113_run(const Shadow7113Input*,unsigned maxframes);
uint64_t shadow7113_pack_ms(uint64_t milliseconds);
#endif
