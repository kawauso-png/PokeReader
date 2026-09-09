#include "manual7121.h"
static bool manual7121_active=false;
static Manual7121 manual7121_control;
static unsigned manual7121_frames=0;
static bool manual7121_released=false;
static void manual7121_panel(void){
    char line[40];snprintf(line,sizeof(line),"FRAME %u - L: STEP",manual7121_frames);
    v7102_panel("S7121 MANUAL PAUSED",line,"START: RUN  SELECT: MAC");
}
static void manual7121_enter(void){
    gate7119_disable();gate7113_cancel();
    mac7118_export_pending=false;
    rank7108_hunting=false;suicune_live_pass_ready=false;
    suicune_root_lock_active=false;suicune_root_lock_ready=false;suicune_root_lock_failed=true;
    suicune_neutral_probe_pending=false;suicune_neutral_probe_remaining=0;
    suicune_wait_up_after_b=false;fixed_armed=false;fixed_run_pending=false;fixed_frames_remaining=0;
    suicune_auto_resume_pending=false;suicune_release_resume_pending=false;
    suicune_early_gate_pending=false;suicune_phase_lock_active=false;suicune_start_phase_lock_active=false;
    manual7121_active=true;manual7121_control.pending=0;
    manual7121_frames=0;manual7121_released=false;
    manual7121_panel();
}
