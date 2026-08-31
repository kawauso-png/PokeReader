#!/usr/bin/env python3
from pathlib import Path

main_path = Path('3gx/sources/main.c')
hook_path = Path('reader_core/src/crystal/hook.rs')
bind_path = Path('reader_core/src/pnp/bindings.rs')
input_path = Path('reader_core/src/pnp/input.rs')
trace_path = Path('reader_core/src/crystal/trace.rs')

m = main_path.read_text(); h = hook_path.read_text(); b = bind_path.read_text(); i = input_path.read_text(); t = trace_path.read_text()

def rep(src, old, new, label):
    n=src.count(old)
    if n!=1: raise SystemExit(f'{label}: expected 1 match, got {n}')
    return src.replace(old,new,1)

# v5.9 Early: falsified v5.8 parity selector -> measured mapper sweep.
m = rep(m, '''    // Closed-loop rule from 0060-0066: odd DIV -> E08, even DIV -> E09.
    suicune_early_phase_slot = suicune_early_pre_div_parity ? 8 : 9;
    suicune_early_slot_used = suicune_early_phase_slot;
    // A = even/E09, B = odd/E08.  v5.7's wider profile sequence is bypassed
    // in adaptive mode but its telemetry plumbing is retained.
    suicune_early_profile_used = suicune_early_pre_div_parity ? 1 : 0;''', '''    // v5.9: v5.8 parity adaptation was falsified by 0067-0071.  Use the
    // already-latched v5.7 mapper profile instead and keep pre-phase telemetry.
    suicune_early_slot_used = suicune_early_phase_slot;''', 'remove false parity selector')
m = rep(m, '''    // v5.8 adaptive mode does not consume the v5.7 sweep sequence.
    if (!suicune_early_control_enabled) return;''', '''    // Consume a profile only on a real gate, so aborted Y+X arms do not skip it.
    if (suicune_early_gate_requests == 1)
        suicune_early_profile_next = (suicune_early_profile_next + 1) % 10;
    if (!suicune_early_control_enabled) return;''', 'restore mapper consumption')

# v5.9 Endpoint phase controller. R schedules release at Q00/Q04/Q08/Q12.
anchor = 'u32 host_early_pre_div_parity(void) { return suicune_early_pre_div_parity; }\n'
block = anchor + '''\n// Suicune Endpoint Phase Lab v5.9.\nstatic bool suicune_endpoint_gate_pending = false;\nstatic u32 suicune_endpoint_profile_next = 0;\nstatic u32 suicune_endpoint_profile_used = 0;\nstatic u32 suicune_endpoint_phase_slot = 0;\nstatic u64 suicune_endpoint_request_tick = 0;\nstatic u64 suicune_endpoint_anchor_tick = 0;\nstatic u64 suicune_endpoint_r_tick = 0;\nstatic u64 suicune_endpoint_target_tick = 0;\nstatic u64 suicune_endpoint_actual_tick = 0;\nstatic u64 suicune_endpoint_first_top_tick = 0;\nstatic bool suicune_endpoint_capture_next_top = false;\n\nvoid host_suicune_endpoint_pause_request(void)\n{\n    static const u32 endpoint_slots[4] = {0, 4, 8, 12};\n    suicune_endpoint_profile_used = suicune_endpoint_profile_next & 3;\n    suicune_endpoint_phase_slot = endpoint_slots[suicune_endpoint_profile_used];\n    suicune_endpoint_profile_next = (suicune_endpoint_profile_next + 1) & 3;\n    suicune_endpoint_request_tick = svcGetSystemTick();\n    suicune_endpoint_anchor_tick = suicune_start_last_top_tick;\n    suicune_endpoint_r_tick = 0;\n    suicune_endpoint_target_tick = 0;\n    suicune_endpoint_actual_tick = 0;\n    suicune_endpoint_first_top_tick = 0;\n    suicune_endpoint_capture_next_top = false;\n    suicune_endpoint_gate_pending = true;\n    is_paused = true;\n}\n\nu32 host_endpoint_profile_used(void) { return suicune_endpoint_profile_used; }\nu32 host_endpoint_phase_slot(void) { return suicune_endpoint_phase_slot; }\nu64 host_endpoint_request_tick(void) { return suicune_endpoint_request_tick; }\nu64 host_endpoint_anchor_tick(void) { return suicune_endpoint_anchor_tick; }\nu64 host_endpoint_r_tick(void) { return suicune_endpoint_r_tick; }\nu64 host_endpoint_target_tick(void) { return suicune_endpoint_target_tick; }\nu64 host_endpoint_actual_tick(void) { return suicune_endpoint_actual_tick; }\nu64 host_endpoint_first_top_tick(void) { return suicune_endpoint_first_top_tick; }\n'''
m = rep(m, anchor, block, 'add endpoint controller state')

needle = '''        if (suicune_early_gate_pending)\n        {'''
insert = '''        if (suicune_endpoint_gate_pending)\n        {\n            if (just_pressed & KEY_R)\n            {\n                u64 now = svcGetSystemTick();\n                u64 offset = (SUICUNE_PHASE_PERIOD_TICKS * (u64)suicune_endpoint_phase_slot) / SUICUNE_PHASE_SLOTS;\n                u64 target = suicune_endpoint_anchor_tick + offset;\n                suicune_endpoint_r_tick = now;\n                if (target <= now + 4096ULL)\n                {\n                    u64 delta = (now + 4096ULL) - target;\n                    target += (delta / SUICUNE_PHASE_PERIOD_TICKS + 1ULL) * SUICUNE_PHASE_PERIOD_TICKS;\n                }\n                suicune_endpoint_target_tick = target;\n                while (svcGetSystemTick() < target) { }\n                suicune_endpoint_actual_tick = svcGetSystemTick();\n                suicune_endpoint_capture_next_top = true;\n                suicune_endpoint_gate_pending = false;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }\n\n        if (suicune_early_gate_pending)\n        {'''
m = rep(m, needle, insert, 'add endpoint R phase gate')

needle = '''        if (suicune_early_capture_next_top)\n        {\n            suicune_early_first_top_tick = top_tick;\n            suicune_early_capture_next_top = false;\n        }'''
insert = needle + '''\n        if (suicune_endpoint_capture_next_top)\n        {\n            suicune_endpoint_first_top_tick = top_tick;\n            suicune_endpoint_capture_next_top = false;\n        }'''
m = rep(m, needle, insert, 'capture endpoint first top')

# Bindings and Rust pnp wrapper for Endpoint timing.
b = rep(b, '''    pub fn host_request_pause();\n    pub fn host_suicune_early_gate_request(pre_ap4: u32);''', '''    pub fn host_request_pause();\n    pub fn host_suicune_endpoint_pause_request();\n    pub fn host_endpoint_profile_used() -> u32;\n    pub fn host_endpoint_phase_slot() -> u32;\n    pub fn host_endpoint_request_tick() -> u64;\n    pub fn host_endpoint_anchor_tick() -> u64;\n    pub fn host_endpoint_r_tick() -> u64;\n    pub fn host_endpoint_target_tick() -> u64;\n    pub fn host_endpoint_actual_tick() -> u64;\n    pub fn host_endpoint_first_top_tick() -> u64;\n    pub fn host_suicune_early_gate_request(pre_ap4: u32);''', 'endpoint binding declarations')
b = rep(b, '''    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_suicune_early_gate_request(_pre_ap4: u32) {}''', '''    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_suicune_endpoint_pause_request() {}\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_profile_used() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_phase_slot() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_request_tick() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_anchor_tick() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_r_tick() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_target_tick() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_actual_tick() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_endpoint_first_top_tick() -> u64 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_early_gate_request(_pre_ap4: u32) {}''', 'endpoint binding stubs')

i += '''\n\n/// Suicune Endpoint Phase Lab v5.9 timing metrics.\npub struct EndpointControlMetrics {\n    pub profile_used: u32,\n    pub slot: u32,\n    pub request_tick: u64,\n    pub anchor_tick: u64,\n    pub r_tick: u64,\n    pub target_tick: u64,\n    pub actual_tick: u64,\n    pub first_top_tick: u64,\n}\n\npub fn request_suicune_endpoint_pause() {\n    unsafe { bindings::host_suicune_endpoint_pause_request() }\n}\n\npub fn endpoint_control_metrics() -> EndpointControlMetrics {\n    EndpointControlMetrics {\n        profile_used: unsafe { bindings::host_endpoint_profile_used() },\n        slot: unsafe { bindings::host_endpoint_phase_slot() },\n        request_tick: unsafe { bindings::host_endpoint_request_tick() },\n        anchor_tick: unsafe { bindings::host_endpoint_anchor_tick() },\n        r_tick: unsafe { bindings::host_endpoint_r_tick() },\n        target_tick: unsafe { bindings::host_endpoint_target_tick() },\n        actual_tick: unsafe { bindings::host_endpoint_actual_tick() },\n        first_top_tick: unsafe { bindings::host_endpoint_first_top_tick() },\n    }\n}\n'''

t = rep(t, '''                endpoint_fast_tail_start();\n                pnp::request_pause();''', '''                endpoint_fast_tail_start();\n                pnp::request_suicune_endpoint_pause();''', 'use endpoint pause controller')

# PURETAIL calibration sentinel: store only pc+DIV for 6/8 final Random reads.
h = rep(h, 'static mut ENDPOINT_FAST_CALLS: u8 = 0;', '''static mut ENDPOINT_FAST_CALLS: u8 = 0;\nconst ENDPOINT_TAIL_SAMPLE_LEN: usize = 8;\nstatic mut ENDPOINT_TAIL_SAMPLE_COUNT: u8 = 0;\nstatic mut ENDPOINT_TAIL_PC: [u16; ENDPOINT_TAIL_SAMPLE_LEN] = [0; ENDPOINT_TAIL_SAMPLE_LEN];\nstatic mut ENDPOINT_TAIL_DIV: [u8; ENDPOINT_TAIL_SAMPLE_LEN] = [0; ENDPOINT_TAIL_SAMPLE_LEN];''', 'add tail sentinel buffers')
h = rep(h, '''        ENDPOINT_FAST_CALLS = 0;\n        ENDPOINT_FAST_TAIL = true;''', '''        ENDPOINT_FAST_CALLS = 0;\n        ENDPOINT_TAIL_SAMPLE_COUNT = 0;\n        ENDPOINT_FAST_TAIL = true;''', 'reset tail sentinel')
h = rep(h, '''pub fn endpoint_fast_tail_calls() -> u8 {\n    unsafe { ENDPOINT_FAST_CALLS }\n}\n\npub fn endpoint_fast_tail_stop() {''', '''pub fn endpoint_fast_tail_calls() -> u8 {\n    unsafe { ENDPOINT_FAST_CALLS }\n}\n\npub fn endpoint_tail_sample_count() -> u8 {\n    unsafe { ENDPOINT_TAIL_SAMPLE_COUNT }\n}\n\npub fn endpoint_tail_sample(index: usize) -> (u16, u8) {\n    unsafe {\n        if index >= ENDPOINT_TAIL_SAMPLE_COUNT as usize || index >= ENDPOINT_TAIL_SAMPLE_LEN { return (0, 0); }\n        (ENDPOINT_TAIL_PC[index], ENDPOINT_TAIL_DIV[index])\n    }\n}\n\npub fn endpoint_fast_tail_stop() {''', 'expose tail sentinel')
h = rep(h, '''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {\n        // Count only Random's first rDIV read.  No DIV/state/tick/mcycle reads\n        // are performed in PURETAIL mode; this single host byte increment is\n        // retained solely to distinguish the 3-call and 4-call item branch.\n        if pc == 0x2f60 {\n            unsafe { ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1) };\n        }\n        return;\n    }''', '''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {\n        // v5.9: one DIV read plus tiny stores; no host tick/mcycle/state/deep log.\n        let div = reader.div();\n        unsafe {\n            let idx = ENDPOINT_TAIL_SAMPLE_COUNT as usize;\n            if idx < ENDPOINT_TAIL_SAMPLE_LEN {\n                ENDPOINT_TAIL_PC[idx] = pc;\n                ENDPOINT_TAIL_DIV[idx] = div;\n                ENDPOINT_TAIL_SAMPLE_COUNT = ENDPOINT_TAIL_SAMPLE_COUNT.saturating_add(1);\n            }\n            if pc == 0x2f60 { ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1); }\n        }\n        return;\n    }''', 'record lightweight tail DIVs')

t = rep(t, '''    endpoint_fast_tail_start, endpoint_fast_tail_stop, measured_div, rng_advance, sdiv_cycles,\n    sdiv_subtick, sdiv_tick, sub_div_tracker,''', '''    endpoint_fast_tail_start, endpoint_fast_tail_stop, endpoint_tail_sample,\n    endpoint_tail_sample_count, measured_div, rng_advance, sdiv_cycles, sdiv_subtick, sdiv_tick,\n    sub_div_tracker,''', 'import tail sentinel')

old = '''        let profile = match em.pre_div_parity {\n            0 => "EVEN",\n            1 => "ODD",\n            _ => "?",\n        };'''
new = '''        let profile = match em.profile_used {\n            0 => "A", 1 => "B", 2 => "C", 3 => "D", 4 => "E",\n            5 => "F", 6 => "G", 7 => "H", 8 => "I", 9 => "J", _ => "?",\n        };'''
if t.count(old) != 2: raise SystemExit(f'profile matches: expected 2, got {t.count(old)}')
t = t.replace(old,new)
t = t.replace('ADAPT,V58,', 'PLAN,V59,')
t = t.replace('MAP,V58,', 'MAP,V59,')
t = t.replace('EARLY,V58,', 'EARLY,V59,')

needle = '''        let _ = write!(\n            line,\n            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"\n        );'''
insert = '''        let epm = pnp::endpoint_control_metrics();\n        let ep_err = epm.actual_tick as i128 - epm.target_tick as i128;\n        let ep_wait = epm.actual_tick.saturating_sub(epm.r_tick);\n        let ep_top = epm.first_top_tick as i128 - epm.actual_tick as i128;\n        line.clear();\n        let _ = write!(line,\n            "endpoint_control,version,profile_index,slot,request_tick,anchor_tick,r_tick,target_tick,actual_tick,error_ticks,wait_ticks,first_top_tick,actual_to_first_top\\n"\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line,\n            "EPC,V59,{},{},{},{},{},{},{},{},{},{},{}\\n",\n            epm.profile_used, epm.slot, epm.request_tick, epm.anchor_tick, epm.r_tick,\n            epm.target_tick, epm.actual_tick, ep_err, ep_wait, epm.first_top_tick, ep_top\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line, "tail_index,pc,div\\n");\n        pnp::trace_file_write(line.as_bytes());\n        let tail_n = endpoint_tail_sample_count() as usize;\n        for tail_i in 0..tail_n {\n            let (pc, div) = endpoint_tail_sample(tail_i);\n            line.clear();\n            let _ = write!(line, "{},{:04X},{:02X}\\n", tail_i, pc, div);\n            pnp::trace_file_write(line.as_bytes());\n        }\n        line.clear();\n        let _ = write!(line, "\\n");\n        pnp::trace_file_write(line.as_bytes());\n\n        let _ = write!(\n            line,\n            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"\n        );'''
t = rep(t, needle, insert, 'insert endpoint control CSV and tail sentinel')

main_path.write_text(m); hook_path.write_text(h); bind_path.write_text(b); input_path.write_text(i); trace_path.write_text(t)
print('Applied Suicune Dual Investigation v5.9')
