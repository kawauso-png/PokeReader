#ifndef RANK7108_CORE_H
#define RANK7108_CORE_H
#include <stdint.h>
uint32_t rank7108_audio(const uint8_t*,uint32_t,const uint8_t*,const uint8_t*,uint32_t*,uint8_t*);
uint32_t rank7108_score(uint16_t seed,int cost,int exclude);
uint32_t rank7108_rank(uint16_t dv);
uint32_t rank7108_best_rank(void);
uint16_t rank7108_best_shiny(void);
uint32_t rank7108_support(void);
uint16_t rank7108_top(unsigned i);
double rank7108_weight(uint16_t dv);
const char *rank7108_model_id(void);
#endif
