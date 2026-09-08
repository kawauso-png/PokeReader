#ifndef RANK7108_RUNTIME_H
#define RANK7108_RUNTIME_H
#include <stdint.h>
void rank7108_begin(void);
int rank7108_evaluate(void); /* 1 candidate, 0 reject, -1 diagnostic stop */
int rank7108_commit(void);   /* durable PRE record before physical UP */
uint32_t rank7108_error(void);
uint32_t rank7108_checks(void);
uint32_t rank7108_cycles(void);
void rank7108_append_result(uint32_t advance,uint32_t present,uint32_t dv);
#endif
