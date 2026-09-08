#ifndef PREFIX7117_H
#define PREFIX7117_H
#include <stdint.h>
/* Proposal count only. Never authorizes real input or selects a DV. */
unsigned prefix7117_offers(uint16_t seed,uint16_t phase);
unsigned prefix7117_model_count(void);
#endif
