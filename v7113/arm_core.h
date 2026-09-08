#ifndef ARM7113_H
#define ARM7113_H
#include <stdint.h>
typedef struct {uint32_t r[16],flags,error,error_pc,error_op;uint64_t steps;} Arm7113;
typedef uint32_t (*ArmRead)(uint32_t,unsigned);
typedef void (*ArmWrite)(uint32_t,uint32_t,unsigned);
void arm7113_step(Arm7113*,ArmRead,ArmWrite);
#endif
