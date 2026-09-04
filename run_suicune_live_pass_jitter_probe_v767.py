from pathlib import Path

# v7.6.7 is applied on top of the fully generated v7.6.6 tree. The current
# operator flow is v7.3.3 TwoStageArm (B-only ARM -> UP-only run), not the old
# Y+X block. Rewrite only the C-control section of the v7.6.7 apply script so
# the Rust/trace changes stay identical while the live pass uses the current UI.

src_path = Path('apply_suicune_live_pass_jitter_probe_v767.py')
s = src_path.read_text()

start = s.index('# C header + pause-loop control.')
end = s.index('# Trace: auto-stop/save', start)

replacement = r'''# C header + current TwoStageArm control. B alone arms both the ordinary
# Suicune trace and v7.6.7 live-pass telemetry. After B is released, physical
# UP alone resumes the VC continuously; the old paused Exact2F scheduler is
# deliberately bypassed. The GB-read hook masks UP for 16 RNG advances, passes
# it for exactly 2 advances, then masks it again.
P = Path('3gx/includes/pokereader.h')
p = P.read_text()
if 'void arm_suicune_live_pass();' not in p:
    p = p.replace('void arm_suicune_probe();', 'void arm_suicune_probe();\nvoid arm_suicune_live_pass();')
P.write_text(p)

C = Path('3gx/sources/main.c')
c = C.read_text()


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
        needle + '            arm_suicune_live_pass();\n',
        1,
    )

# Current v7.3.3 B-only authoritative-root arm.
c = replace_braced_block(
    c,
    '        if ((held & KEY_B) && !(held & KEY_Y)',
    arm_transform,
    'B-arm block',
)


def stage2_transform(_block):
    return '''        // v7.6.7 stage 2: once B is fully released and physical UP is the\n        // only input, resume normal VC execution. UP is already armed in the\n        // Rust GB-read filter, so it is hidden for 16 advances, visible for\n        // exactly 2 advances, then hidden again. No R and no paused frame-run.\n        if (suicune_wait_up_after_b)\n        {\n            const u32 stage2_block = KEY_A | KEY_B | KEY_X | KEY_Y |\n                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R |\n                KEY_START | KEY_SELECT;\n            if ((held & stage2_block) != 0)\n            {\n                svcSleepThread(1000000);\n                continue;\n            }\n            if (held & KEY_DUP)\n            {\n                suicune_wait_up_after_b = false;\n                fixed_frames_remaining = 0;\n                fixed_run_pending = false;\n                fixed_armed = false;\n                suicune_auto_resume_pending = false;\n                suicune_phase_lock_active = false;\n                suicune_start_phase_lock_active = false;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }'''

c = replace_braced_block(
    c,
    '        if (suicune_wait_up_after_b)',
    stage2_transform,
    'UP stage2 block',
)
C.write_text(c)

'''

patched = s[:start] + replacement + s[end:]
exec(compile(patched, str(src_path), 'exec'), {'__name__': '__main__'})
