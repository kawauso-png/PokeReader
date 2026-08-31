#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
bind_path = Path('reader_core/src/pnp/bindings.rs')
input_path = Path('reader_core/src/pnp/input.rs')
trace_path = Path('reader_core/src/crystal/trace.rs')

m = main_path.read_text()
b = bind_path.read_text()
i = input_path.read_text()
t = trace_path.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# Robust Y+B chord and per-encounter validity.
m = rep(m,
'''static bool suicune_delay_ready = false;\n\n#define SUICUNE_DIV_PTR_SLOT''',
'''static bool suicune_delay_ready = false;\nstatic bool suicune_delay_chord_latched = false;\nstatic bool suicune_delay_encounter_valid = false;\n\n#define SUICUNE_DIV_PTR_SLOT''',
'add robust chord state')

m = rep(m,
'''u32 host_suicune_delay_ready(void) { return suicune_delay_ready ? 1 : 0; }\n''',
'''u32 host_suicune_delay_ready(void) { return suicune_delay_ready ? 1 : 0; }\nu32 host_suicune_delay_encounter_valid(void) { return suicune_delay_encounter_valid ? 1 : 0; }\n''',
'export encounter validity')

# Reset chord latch whenever the chord is no longer physically held. This
# makes either key order work: Y->B or B->Y.
m = rep(m,
'''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if (suicune_delay_pending)''',
'''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if ((held & (KEY_Y | KEY_B)) != (KEY_Y | KEY_B))\n        {\n            suicune_delay_chord_latched = false;\n        }\n\n        if (suicune_delay_pending)''',
'add chord latch reset')

# v6.1 required B's just-pressed edge to occur while Y was already held. That
# is easy to miss with human input. Accept the stable held chord once instead.
m = rep(m,
'''            if (just_pressed & KEY_B)\n            {\n                if (!(held & KEY_DUP))\n                {\n                    suicune_delay_profile_used = suicune_delay_profile_next & 3;\n                    suicune_delay_frames_requested = suicune_delay_profile_used;\n                    suicune_delay_frames_remaining = 0;\n                    suicune_delay_frames_executed = 0;\n                    suicune_delay_pre_div = suicune_live_div_direct();\n                    suicune_delay_pre_sub = suicune_live_sub_direct();\n                    suicune_delay_pre_phase = suicune_live_phase_direct(suicune_delay_pre_div, suicune_delay_pre_sub);\n                    suicune_delay_pre_valid = 1;\n                    suicune_delay_post_valid = 0;\n                    suicune_delay_post_div = 0;\n                    suicune_delay_post_sub = 0;\n                    suicune_delay_post_phase = 0;\n                    suicune_delay_pending = true;\n                    suicune_delay_started = false;\n                    suicune_delay_ready = false;\n                    suicune_delay_run_id++;\n                }\n            }''',
'''            if ((held & KEY_B) && !suicune_delay_chord_latched && !(held & KEY_DUP))\n            {\n                suicune_delay_chord_latched = true;\n                suicune_delay_profile_used = suicune_delay_profile_next & 3;\n                suicune_delay_frames_requested = suicune_delay_profile_used;\n                suicune_delay_frames_remaining = 0;\n                suicune_delay_frames_executed = 0;\n                suicune_delay_pre_div = suicune_live_div_direct();\n                suicune_delay_pre_sub = suicune_live_sub_direct();\n                suicune_delay_pre_phase = suicune_live_phase_direct(suicune_delay_pre_div, suicune_delay_pre_sub);\n                suicune_delay_pre_valid = 1;\n                suicune_delay_post_valid = 0;\n                suicune_delay_post_div = 0;\n                suicune_delay_post_sub = 0;\n                suicune_delay_post_phase = 0;\n                suicune_delay_pending = true;\n                suicune_delay_started = false;\n                suicune_delay_ready = false;\n                suicune_delay_run_id++;\n            }''',
'robust held chord trigger')

# Poll modifier chords at 5 ms instead of 50 ms. The game remains frozen, so
# this changes only UI responsiveness, not emulated timing.
m = rep(m,
'''            svcSleepThread(50000000);\n            continue;\n        }\n\n        if (just_pressed & (KEY_SELECT | KEY_L))''',
'''            svcSleepThread(5000000);\n            continue;\n        }\n\n        if (just_pressed & (KEY_SELECT | KEY_L))''',
'faster paused chord polling')

# Mark whether THIS encounter really consumed a completed neutral delay. If
# Y+B was missed, clear stale metrics so the CSV cannot inherit the previous
# trial and masquerade as valid actuator data.
m = rep(m,
'''                    if (suicune_delay_ready)\n                    {\n                        suicune_delay_profile_next = (suicune_delay_profile_used + 1) & 3;\n                        suicune_delay_ready = false;\n                    }\n                    suicune_observe_reset();''',
'''                    if (suicune_delay_ready)\n                    {\n                        suicune_delay_profile_next = (suicune_delay_profile_used + 1) & 3;\n                        suicune_delay_ready = false;\n                        suicune_delay_encounter_valid = true;\n                    }\n                    else\n                    {\n                        suicune_delay_encounter_valid = false;\n                        suicune_delay_profile_used = 0xffffffff;\n                        suicune_delay_frames_requested = 0;\n                        suicune_delay_frames_executed = 0;\n                        suicune_delay_pre_valid = 0;\n                        suicune_delay_post_valid = 0;\n                        suicune_delay_pre_div = 0;\n                        suicune_delay_pre_sub = 0;\n                        suicune_delay_pre_phase = 0;\n                        suicune_delay_post_div = 0;\n                        suicune_delay_post_sub = 0;\n                        suicune_delay_post_phase = 0;\n                    }\n                    suicune_observe_reset();''',
'bind telemetry to current encounter')

# Rust binding and metrics.
b = rep(b,
'''    pub fn host_suicune_delay_ready() -> u32;\n    pub fn host_suicune_delay_pre_valid() -> u32;''',
'''    pub fn host_suicune_delay_ready() -> u32;\n    pub fn host_suicune_delay_encounter_valid() -> u32;\n    pub fn host_suicune_delay_pre_valid() -> u32;''',
'add validity binding')

b = rep(b,
'''    pub extern "C" fn host_suicune_delay_ready() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_pre_valid() -> u32 { 0 }''',
'''    pub extern "C" fn host_suicune_delay_ready() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_encounter_valid() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_delay_pre_valid() -> u32 { 0 }''',
'add validity stub')

i = rep(i,
'''    pub ready: bool,\n    pub pre_valid: bool,''',
'''    pub ready: bool,\n    pub encounter_valid: bool,\n    pub pre_valid: bool,''',
'extend metrics validity')

i = rep(i,
'''        ready: unsafe { bindings::host_suicune_delay_ready() } != 0,\n        pre_valid: unsafe { bindings::host_suicune_delay_pre_valid() } != 0,''',
'''        ready: unsafe { bindings::host_suicune_delay_ready() } != 0,\n        encounter_valid: unsafe { bindings::host_suicune_delay_encounter_valid() } != 0,\n        pre_valid: unsafe { bindings::host_suicune_delay_pre_valid() } != 0,''',
'populate validity')

# CSV marks current-trial validity explicitly and versions the experiment.
t = rep(t,
'''            "actuator,version,profile,frames_requested,frames_executed,run_id,ready_at_save,pre_valid,pre_div,pre_sub,pre_phase,post_valid,post_div,post_sub,post_phase,phase_delta_m\\n"''',
'''            "actuator,version,encounter_valid,profile,frames_requested,frames_executed,run_id,ready_at_save,pre_valid,pre_div,pre_sub,pre_phase,post_valid,post_div,post_sub,post_phase,phase_delta_m\\n"''',
'add CSV validity header')

t = rep(t,
'''            "ACT,V61B,{},{},{},{},{},{},{:02X},{:02X},{:04X},{},{:02X},{:02X},{:04X},{}\\n",\n            dm.profile_used, dm.frames_requested, dm.frames_executed, dm.run_id, dm.ready as u8,''',
'''            "ACT,V61C,{},{},{},{},{},{},{},{:02X},{:02X},{:04X},{},{:02X},{:02X},{:04X},{}\\n",\n            dm.encounter_valid as u8, dm.profile_used, dm.frames_requested, dm.frames_executed, dm.run_id, dm.ready as u8,''',
'write CSV validity')

for old, new in [
    ('PLAN,V61B,', 'PLAN,V61C,'),
    ('MAP,V61B,', 'MAP,V61C,'),
    ('EARLY,V61B,', 'EARLY,V61C,'),
    ('LIVE,V61B,', 'LIVE,V61C,'),
]:
    if old not in t:
        raise SystemExit(f'missing marker {old}')
    t = t.replace(old, new)

main_path.write_text(m)
bind_path.write_text(b)
input_path.write_text(i)
trace_path.write_text(t)
print('Applied Suicune Neutral Delay v6.1c robust trigger')
