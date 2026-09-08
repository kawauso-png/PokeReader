#!/usr/bin/env python3
from pathlib import Path
p=Path('3gx/sources/main.c');s=p.read_text()
anchor='static bool suicune_hunt_v7110 = false;'
assert anchor in s
s=s.replace(anchor,anchor+'''
static u8 *suicune_hunt_fb_a=NULL, *suicune_hunt_fb_b=NULL;
static u32 suicune_hunt_stride=0, suicune_hunt_format=0;
static bool suicune_hunt_release_drawn=false;
''',1)
anchor='void handle_freeze(bool isTopScreen)'
assert anchor in s
s=s.replace(anchor,'''// Redraw only the existing overlay. Never call run_frame or release a guest frame.
static void suicune_hunt_redraw(void)
{
    if (!suicune_hunt_v7110 || suicune_hunt_fb_a==NULL) return;
    draw_to_screen(0,suicune_hunt_fb_a,suicune_hunt_stride,suicune_hunt_format);
    svcFlushProcessDataCache(CUR_PROCESS_HANDLE,(u32)suicune_hunt_fb_a,SCREEN_WIDTH*SCREEN_HEIGHT);
    if (suicune_hunt_fb_b!=NULL && suicune_hunt_fb_b!=suicune_hunt_fb_a) {
        draw_to_screen(0,suicune_hunt_fb_b,suicune_hunt_stride,suicune_hunt_format);
        svcFlushProcessDataCache(CUR_PROCESS_HANDLE,(u32)suicune_hunt_fb_b,SCREEN_WIDTH*SCREEN_HEIGHT);
    }
}

'''+anchor,1)
anchor='''        if (suicune_exact2_release_waiting())
        {'''
assert anchor in s
s=s.replace(anchor,anchor+'''
            if (suicune_hunt_v7110 && !suicune_hunt_release_drawn) {
                suicune_hunt_redraw();suicune_hunt_release_drawn=true;
            }''',1)
anchor='''                suicune_start_phase_lock_active = false;
                continue;
            }

            // Neutral delay is complete.'''
assert anchor in s
s=s.replace(anchor,'''                suicune_start_phase_lock_active = false;
                suicune_hunt_release_drawn=false;
                suicune_hunt_redraw();
                continue;
            }

            // Neutral delay is complete.''',1)
anchor='''    bool isTopScreen = screenId == 0;
    if (isTopScreen)'''
assert anchor in s
s=s.replace(anchor,'''    bool isTopScreen = screenId == 0;
    if (isTopScreen) {
        suicune_hunt_fb_a=fb_a;suicune_hunt_fb_b=fb_b;
        suicune_hunt_stride=stride;suicune_hunt_format=format;
    }
    if (isTopScreen)''',1)
p.write_text(s)
p=Path('reader_core/src/crystal/trace.rs');s=p.read_text()
anchor='    pub fn draw_rng_status(&self) {\n'
assert anchor in s
s=s.replace(anchor,anchor+'''        unsafe {
            if V7110_HUNT && V7110_FROZEN {
                if let Some(r)=self.probe_result {
                    let shiny=(r.raw_dv&0x0fff)==0x0aaa && ((r.raw_dv>>12)&2)!=0;
                    pnp::println!("H7110 RESULT {}",if shiny {"SHINY"} else {"NONSHINY"});
                    pnp::println!("ACTUAL DV {:04X} ROUTE{}",r.raw_dv,r.route);
                    pnp::println!("CSV {}",pnp::trace_written_slot());
                    pnp::println!("{}",if shiny {"KEEP ENCOUNTER - CAPTURE"} else {"RESET VC FOR NEXT TRY"});
                    return;
                }
            }
        }
''',1)
anchor='''                    pnp::println!("PHYSICAL UP ONLY");'''
assert anchor in s
s=s.replace(anchor,'''                    pnp::println!("{}",if super::hook::exact2_release_waiting() {"RELEASE UP NOW"}
                        else if super::hook::live_pass_telemetry().exact2_release_confirmed!=0 {"NATIVE GENERATION - NO INPUT"}
                        else {"PHYSICAL UP ONLY"});''',1)
p.write_text(s)
print('Frozen UI refresh only: no guest advance, no timing-actuator change; actual DV result shown.')
