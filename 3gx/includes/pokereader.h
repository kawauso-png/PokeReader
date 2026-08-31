#pragma once

#include <3ds.h>

void initialize();
void run_frame();
u32 blue_capture_target(u32 run_id);

// Blue JP fixed-legend selector. 0=Mewtwo, 1=Zapdos, 2=Articuno, 3=Moltres.
u32 host_blue_legend_target_id(void);
u32 host_blue_legend_target_species(void);
u32 host_blue_legend_target_level(void);
void host_blue_legend_target_step(s32 delta);
