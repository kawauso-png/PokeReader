#!/usr/bin/env python3
from pathlib import Path

P = Path('3gx/sources/main.c')
T = Path('reader_core/src/crystal/trace.rs')
m = P.read_text()
t = T.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v733 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


def replace_braced_block(src, marker, new_block, label):
    a = src.find(marker)
    if a < 0:
        raise SystemExit(f'v733 {label}: marker not found')
    b = src.find('{', a)
    if b < 0:
        raise SystemExit(f'v733 {label}: opening brace not found')
    depth = 0
    end = -1
    for i in range(b, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise SystemExit(f'v733 {label}: closing brace not found')
    return src[:a] + new_block + src[end:]

# New two-stage state: B arms while frozen; only a later physical UP starts Exact-2F.
old = '''static bool suicune_root_lock_active = false;\nstatic bool suicune_root_lock_ready = false;\nstatic bool suicune_root_lock_failed = false;'''
new = '''static bool suicune_root_lock_active = false;\nstatic bool suicune_root_lock_ready = false;\nstatic bool suicune_root_lock_failed = false;\nstatic bool suicune_wait_up_after_b = false;'''
m = rep(m, old, new, 'two-stage state declaration')

# Replace the generated v7.2.4/v7.3.2 simultaneous UP+B block by locating the
# condition and balancing braces. This is intentionally whitespace-independent.
marker = '        if ((held & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)'
new_block = '''        // v7.3.3 two-stage arm: B alone captures/arms the authoritative\n        // frozen A/r10 root. UP is supplied later as a separate physical\n        // action, eliminating the unreliable simultaneous UP+B chord.\n        if ((held & KEY_B) && !(held & KEY_Y)\n            && suicune_root_lock_ready\n            && !suicune_wait_up_after_b\n            && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            suicune_root_lock_ready = false;\n            suicune_root_lock_active = false;\n            arm_suicune_probe();\n            suicune_observe_reset();\n            suicune_early_lab_reset();\n            suicune_obs_arm_tick = svcGetSystemTick();\n            fixed_a_frames = 2;\n            fixed_frames_remaining = 0;\n            fixed_armed = true;\n            fixed_run_pending = false;\n            suicune_auto_resume_pending = false;\n            suicune_wait_up_after_b = true;\n            suicune_phase_lock_active = true;\n            suicune_phase_anchor_tick = 0;\n            suicune_phase_target_tick = 0;\n            suicune_phase_actual_tick = 0;\n            suicune_start_phase_lock_active = true;\n            suicune_start_phase_anchor_tick = suicune_start_last_top_tick;\n            suicune_start_phase_target_tick = 0;\n            suicune_start_phase_actual_tick = 0;\n            continue;\n        }'''
m = replace_braced_block(m, marker, new_block, 'replace UP+B with B-only arm')

# Insert a dedicated wait state immediately before the existing fixed_run_pending
# handler. B must be released first; then UP alone latches Exact-2F. No game frame
# is released while waiting for this second stage.
anchor = '''        // Y+L schedules a fixed run, but do not let a game frame through while\n        // either trigger modifier is still physically held.  This avoids the\n'''
block = '''        // v7.3.3 stage 2: after B-only ARM, wait frozen until B is fully\n        // released and physical UP is held. Then hand off to the unchanged\n        // Exact-2F scheduler. UP is intentionally excluded from its modifier\n        // release gate, so the two VC frames contain UP and no B.\n        if (suicune_wait_up_after_b)\n        {\n            const u32 stage2_block = KEY_A | KEY_B | KEY_X | KEY_Y |\n                KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT | KEY_L | KEY_R |\n                KEY_START | KEY_SELECT;\n            if ((held & stage2_block) != 0)\n            {\n                svcSleepThread(1000000);\n                continue;\n            }\n            if (held & KEY_DUP)\n            {\n                suicune_wait_up_after_b = false;\n                fixed_run_pending = true;\n                suicune_auto_resume_pending = true;\n                continue;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }\n\n'''
if m.count(anchor) != 1:
    raise SystemExit(f'v733 fixed-run anchor count {m.count(anchor)}')
m = m.replace(anchor, block + anchor, 1)

# Fresh scans/manual resumes must not inherit stage-2 state.
m = rep(m,
'''                suicune_root_lock_failed = false;\n                suicune_root_lock_steps = 0;''',
'''                suicune_root_lock_failed = false;\n                suicune_wait_up_after_b = false;\n                suicune_root_lock_steps = 0;''',
'reset stage2 on scan')

m = rep(m,
'''            suicune_root_lock_active = false;\n            suicune_root_lock_ready = false;\n            suicune_root_lock_failed = false;\n            break;''',
'''            suicune_root_lock_active = false;\n            suicune_root_lock_ready = false;\n            suicune_root_lock_failed = false;\n            suicune_wait_up_after_b = false;\n            break;''',
'clear stage2 on manual resume')

# User-facing instructions: no simultaneous chord anymore.
t = t.replace('UP+B RUN', 'B ARM -> UP').replace('UP+B DONOR', 'B ARM -> UP')
t = t.replace('S732 A/r10 LOCKED', 'S733 A/r10 LOCKED')
t = t.replace('S732 ROOTLOCK SCAN', 'S733 ROOTLOCK SCAN')

P.write_text(m)
T.write_text(t)
print('Applied Suicune v7.3.3 TwoStageArm: B-only ARM, then UP-only Exact-2F')
