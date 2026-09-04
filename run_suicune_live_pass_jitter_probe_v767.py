from pathlib import Path

src_path = Path('apply_suicune_live_pass_jitter_probe_v767.py')
s = src_path.read_text()

def replace_once(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767 wrapper {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# Safety: only FF97 (hUnusedByte) may be used as the zero shadow.
fn_start = s.index('fn find_zero_hram_addr() -> u16 {')
fn_end = s.index('\npub fn arm_live_pass_probe()', fn_start)
zero_fn = r'''fn find_zero_hram_addr() -> u16 {
    let base = pnp::read::<u32>(CRYSTAL_HRAM_PTR);
    if base == 0 || !pnp::is_memory_mapped(base) {
        return 0;
    }
    const ZERO_SHADOW_GB: u16 = 0xff97;
    let host = base.wrapping_add((ZERO_SHADOW_GB as u32).wrapping_sub(HRAM_GB_BASE));
    if pnp::is_memory_mapped(host) && pnp::read::<u8>(host) == 0 {
        ZERO_SHADOW_GB
    } else {
        0
    }
}
'''
s = s[:fn_start] + zero_fn + s[fn_end:]

# Safety: fail closed if the shadow is unavailable/non-zero.
arm_start = s.index('pub fn arm_live_pass_probe() {')
arm_end = s.index('\npub fn live_pass_telemetry()', arm_start)
arm_fn = r'''pub fn arm_live_pass_probe() -> bool {
    let base = rng_advance();
    let zero = find_zero_hram_addr();
    let ok = zero != 0;
    unsafe {
        LIVE_PASS = LivePassTelemetry {
            armed_advance: base,
            delay_frames: LIVE_PASS_DELAY_FRAMES,
            width_frames: LIVE_PASS_WIDTH_FRAMES,
            pass_start_advance: base.wrapping_add(LIVE_PASS_DELAY_FRAMES),
            pass_end_advance: base
                .wrapping_add(LIVE_PASS_DELAY_FRAMES)
                .wrapping_add(LIVE_PASS_WIDTH_FRAMES),
            zero_addr: zero,
            zero_ok: ok as u8,
            ..LivePassTelemetry::EMPTY
        };
        LIVE_PASS_ARMED = ok;
    }
    ok
}
'''
s = s[:arm_start] + arm_fn + s[arm_end:]

old_ffi = '''#[no_mangle]\\npub extern "C" fn arm_suicune_live_pass() {\\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\\n        crystal::arm_live_pass_probe();\\n    }\\n}\\n\\n'''
new_ffi = '''#[no_mangle]\\npub extern "C" fn arm_suicune_live_pass() -> u32 {\\n    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {\\n        return crystal::arm_live_pass_probe() as u32;\\n    }\\n    0\\n}\\n\\n'''
s = replace_once(s, old_ffi, new_ffi, 'FFI readiness')

# Telemetry: prove how many distinct RNG advances actually contained passed hJoy reads.
s = replace_once(
    s,
    '    pub passed_reads: u32,\\n    pub first_mask_advance: u32,\\n',
    '    pub passed_reads: u32,\\n    pub pass_advances: u8,\\n    pub last_pass_advance: u32,\\n    pub first_mask_advance: u32,\\n',
    'telemetry fields',
)
s = replace_once(
    s,
    '        passed_reads: 0,\\n        first_mask_advance: 0,\\n',
    '        passed_reads: 0,\\n        pass_advances: 0,\\n        last_pass_advance: 0,\\n        first_mask_advance: 0,\\n',
    'telemetry defaults',
)
s = replace_once(
    s,
    '        if in_pass {\\n            LIVE_PASS.passed_reads = LIVE_PASS.passed_reads.wrapping_add(1);\\n',
    '''        if in_pass {\\n            LIVE_PASS.passed_reads = LIVE_PASS.passed_reads.wrapping_add(1);\\n            if LIVE_PASS.pass_advances == 0 || LIVE_PASS.last_pass_advance != now {\\n                LIVE_PASS.pass_advances = LIVE_PASS.pass_advances.saturating_add(1);\\n                LIVE_PASS.last_pass_advance = now;\\n            }\\n''',
    'distinct pass advances',
)

s = replace_once(
    s,
    'zero_ok,joy_reads,masked_reads,passed_reads,first_mask_advance',
    'zero_ok,joy_reads,masked_reads,passed_reads,pass_advances,last_pass_advance,first_mask_advance',
    'CSV header pass advances',
)
s = replace_once(
    s,
    'LIVEPASS,V767,{},{},{},{},{},{:04X},{},{},{},{},{},{},{:02X}',
    'LIVEPASS,V767,{},{},{},{},{},{:04X},{},{},{},{},{},{},{},{:02X}',
    'CSV format pass advances',
)
s = replace_once(
    s,
    '            lp.passed_reads,\\n            lp.first_mask_advance,\\n',
    '            lp.passed_reads,\\n            lp.pass_advances,\\n            lp.last_pass_advance,\\n            lp.first_mask_advance,\\n',
    'CSV args pass advances',
)

# Current operator flow: v7.3.3 TwoStageArm (B-only ARM -> UP-only run).
start = s.index('# C header + pause-loop control.')
end = s.index('# Trace: auto-stop/save', start)

replacement = r'''# C header + current TwoStageArm control.
P = Path('3gx/includes/pokereader.h')
p = P.read_text()
if 'u32 arm_suicune_live_pass();' not in p:
    p = p.replace(
        'void arm_suicune_probe();',
        'void arm_suicune_probe();\nu32 arm_suicune_live_pass();'
    )
P.write_text(p)

C = Path('3gx/sources/main.c')
c = C.read_text()

state_anchor = 'static bool suicune_wait_up_after_b = false;\n'
if state_anchor not in c:
    raise SystemExit('v767 live-pass-ready state anchor missing')
c = c.replace(
    state_anchor,
    state_anchor + 'static bool suicune_live_pass_ready = false;\n',
    1,
)

def replace_braced_block(src, marker, transform, label):
    a = src.find(marker)
    if a < 0:
        raise SystemExit(f'v767 {label}: marker not found')
    b = src.find('{', a)
    if b < 0:
        raise SystemExit(f'v767 {label}: opening brace not found')
    depth = 0
    stop = -1
    for i in range(b, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                stop = i + 1
                break
    if stop < 0:
        raise SystemExit(f'v767 {label}: closing brace not found')
    old_block = src[a:stop]
    new_block = transform(old_block)
    return src[:a] + new_block + src[stop:]

def arm_transform(block):
    needle = '            arm_suicune_probe();\n'
    if needle not in block:
        raise SystemExit('v767 B-arm: arm_suicune_probe missing')
    return block.replace(
        needle,
        needle + '            suicune_live_pass_ready = arm_suicune_live_pass() != 0;\n',
        1,
    )

c = replace_braced_block(
    c,
    '        if ((held & KEY_B) && !(held & KEY_Y)',
    arm_transform,
    'B-arm block',
)

def stage2_transform(_block):
    return (
        '        // v7.6.7: continuous run, fail closed on shadow validation.\n'
        '        if (suicune_wait_up_after_b)\n'
        '        {\n'
        '            const u32 stage2_block = KEY_A | KEY_B | KEY_X | KEY_Y |\n'
        '                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R |\n'
        '                KEY_START | KEY_SELECT;\n'
        '            if ((held & stage2_block) != 0)\n'
        '            {\n'
        '                svcSleepThread(1000000);\n'
        '                continue;\n'
        '            }\n'
        '            if (held & KEY_DUP)\n'
        '            {\n'
        '                if (!suicune_live_pass_ready)\n'
        '                {\n'
        '                    svcSleepThread(1000000);\n'
        '                    continue;\n'
        '                }\n'
        '                suicune_wait_up_after_b = false;\n'
        '                fixed_frames_remaining = 0;\n'
        '                fixed_run_pending = false;\n'
        '                fixed_armed = false;\n'
        '                suicune_auto_resume_pending = false;\n'
        '                suicune_phase_lock_active = false;\n'
        '                suicune_start_phase_lock_active = false;\n'
        '                is_paused = false;\n'
        '                break;\n'
        '            }\n'
        '            svcSleepThread(1000000);\n'
        '            continue;\n'
        '        }'
    )

c = replace_braced_block(
    c,
    '        if (suicune_wait_up_after_b)',
    stage2_transform,
    'UP stage2 block',
)
C.write_text(c)

'''

s = s[:start] + replacement + s[end:]

# Robust trace stop anchor: do not depend on adjacency to `self.len += 1`.
old_trace_start = "anchor = '''        self.len += 1;\\\\n\\\\n        if self.probe_active && window[2] == SUICUNE_SPECIES {\\\\n'''"
new_trace_start = "anchor = '''        if self.probe_active && window[2] == SUICUNE_SPECIES {\\\\n'''"
s = replace_once(s, old_trace_start, new_trace_start, 'trace stop anchor')

old_trace_insert = "insert = '''        self.len += 1;\\\\n\\\\n        // Stop soon after the live two-frame window."
new_trace_insert = "insert = '''        // Stop soon after the live two-frame window."
s = replace_once(s, old_trace_insert, new_trace_insert, 'trace stop insertion')

s = replace_once(
    s,
    'pnp::println!(\\"J{} M{} P{} Z{}\\",lp.joy_reads,lp.masked_reads,lp.passed_reads,lp.zero_ok);',
    'pnp::println!(\\"J{} M{} P{} A{} Z{}\\",lp.joy_reads,lp.masked_reads,lp.passed_reads,lp.pass_advances,lp.zero_ok);',
    'UI pass advances',
)

exec(compile(s, str(src_path), 'exec'), {'__name__': '__main__'})
