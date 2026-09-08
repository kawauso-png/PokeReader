#ifndef SNAPSHOT7116_H
#define SNAPSHOT7116_H
#include <stdint.h>
typedef struct {
 uint64_t search_id,clock_ms,clock_tick,launch,resume;
 uint32_t check,advance,seed,rom_base,rom_size,heap_base,hz;
} Snapshot7116Meta;
typedef int (*Snapshot7116Write)(void*,const void*,uint32_t);
int snapshot7116_emit(const Snapshot7116Meta*,const uint8_t*code,const uint8_t*data,const uint8_t*rom,Snapshot7116Write,void*,uint32_t hashes[4]);
int snapshot7116_save(const Snapshot7116Meta*,const uint8_t*code,const uint8_t*data,const uint8_t*rom,uint32_t hashes[4]);
#endif
