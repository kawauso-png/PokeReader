#ifndef GATE7113_H
#define GATE7113_H
#include <stdint.h>
void gate7113_begin(void);
int gate7113_evaluate(void);
int gate7113_log_scan(int decision);
int gate7113_commit(void);
uint32_t gate7113_error(void);
uint32_t gate7113_checks(void);
uint32_t gate7113_dv(void);
uint32_t gate7113_models(void);
uint64_t gate7113_launch_tick(void);
uint64_t gate7113_resume_tick(void);
int gate7113_active(void);
void gate7113_cancel(void);
void gate7113_append_result(uint32_t advance,uint32_t present,uint32_t dv);
#endif
