from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767b {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


# -------------------------------------------------------------------------
# C-side verification: csvc.h declares svcConvertVAToPA used by common.h,
# and verify both the physical alias and ordinary mapped VA observe each
# temporary mask/restore. This catches alias/cache-coherency false positives.
# -------------------------------------------------------------------------
P = Path('3gx/sources/hid.c')
c = P.read_text()
c = rep(c,
        '#include <3ds.h>\n#include "common.h"\n',
        '#include <3ds.h>\n#include "csvc.h"\n#include "common.h"\n',
        'csvc declaration include')

c = rep(c,
'''  if ((*pa & KEY_DUP) != 0)\n  {\n    g_up_mask_begin_failures++;\n    *pa = original;\n    __asm__ volatile("dmb" ::: "memory");\n    return 0;\n  }\n''',
'''  // Both views must agree.  If the ordinary read-only mapping still sees\n  // UP, the emulator may also see stale input, so fail closed.\n  if (((*pa | *g_key_addr) & KEY_DUP) != 0)\n  {\n    g_up_mask_begin_failures++;\n    *pa = original;\n    __asm__ volatile("dmb" ::: "memory");\n    return 0;\n  }\n''',
        'mask dual-view verification')

c = rep(c,
'''  if (*pa != saved)\n  {\n    g_up_mask_restore_failures++;\n    return 0;\n  }\n''',
'''  if (*pa != saved || *g_key_addr != saved)\n  {\n    g_up_mask_restore_failures++;\n    return 0;\n  }\n''',
        'restore dual-view verification')
P.write_text(c)

# -------------------------------------------------------------------------
# Rust hook telemetry: observe Crystal's own hJoypadDown (FF9A) after each
# presented frame.  Observation only; no GB RAM writes.
# -------------------------------------------------------------------------
H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

h = rep(h,
'''    pub first_remask_pc: u16,\n}\n''',
'''    pub first_remask_pc: u16,\n    // Game-side proof: hJoypadDown (FF9A), bit 6 = UP.  These are sampled\n    // once per presented frame by Trace::record after Crystal UpdateJoypad.\n    pub game_observed_advances: u8,\n    pub game_mask_up_advances: u8,\n    pub game_pass_up_advances: u8,\n    pub game_remask_up_advances: u8,\n    pub game_first_mask_hjoy: u8,\n    pub game_first_pass_hjoy: u8,\n    pub game_first_remask_hjoy: u8,\n    pub game_last_observed_advance: u32,\n}\n''',
        'telemetry game fields')

h = rep(h,
'''        first_remask_pc: 0,\n    };\n}\n''',
'''        first_remask_pc: 0,\n        game_observed_advances: 0,\n        game_mask_up_advances: 0,\n        game_pass_up_advances: 0,\n        game_remask_up_advances: 0,\n        game_first_mask_hjoy: 0xff,\n        game_first_pass_hjoy: 0xff,\n        game_first_remask_hjoy: 0xff,\n        game_last_observed_advance: 0,\n    };\n}\n''',
        'telemetry game defaults')

anchor = '''pub fn live_pass_should_finish() -> bool {\n'''
if h.count(anchor) != 1:
    raise SystemExit(f'v767b live finish anchor count {h.count(anchor)}')
observe = r'''/// Observe Crystal's own decoded physical input. hJoypadDown is written by
/// UpdateJoypad after the rJOYP sampling sequence.  This is the authoritative
/// proof that the temporary host HID mask actually reached game logic.
pub fn live_pass_observe_hjoypad_down(hjoy: u8) {
    const PAD_UP: u8 = 0x40;
    unsafe {
        if !LIVE_PASS_ARMED {
            return;
        }
        let now = RNG_ADVANCE;
        if LIVE_PASS.game_observed_advances != 0
            && LIVE_PASS.game_last_observed_advance == now
        {
            return;
        }
        LIVE_PASS.game_last_observed_advance = now;
        LIVE_PASS.game_observed_advances = LIVE_PASS.game_observed_advances.saturating_add(1);

        let before_pass = now.wrapping_sub(LIVE_PASS.pass_start_advance) >= 0x8000_0000;
        let pass_delta = now.wrapping_sub(LIVE_PASS.pass_start_advance);
        let in_pass = pass_delta < LIVE_PASS_FRAMES;
        let after_pass = now.wrapping_sub(LIVE_PASS.pass_end_advance) < 0x8000_0000;
        let up = (hjoy & PAD_UP) != 0;

        if before_pass {
            if LIVE_PASS.game_first_mask_hjoy == 0xff {
                LIVE_PASS.game_first_mask_hjoy = hjoy;
            }
            if up {
                LIVE_PASS.game_mask_up_advances = LIVE_PASS.game_mask_up_advances.saturating_add(1);
            }
        } else if in_pass {
            if LIVE_PASS.game_first_pass_hjoy == 0xff {
                LIVE_PASS.game_first_pass_hjoy = hjoy;
            }
            if up {
                LIVE_PASS.game_pass_up_advances = LIVE_PASS.game_pass_up_advances.saturating_add(1);
            }
        } else if after_pass {
            if LIVE_PASS.game_first_remask_hjoy == 0xff {
                LIVE_PASS.game_first_remask_hjoy = hjoy;
            }
            if up {
                LIVE_PASS.game_remask_up_advances = LIVE_PASS.game_remask_up_advances.saturating_add(1);
            }
        }
    }
}

'''
h = h.replace(anchor, observe + anchor, 1)
H.write_text(h)

# Trace imports observer and samples FF9A once per recorded frame.  gb_mem
# dispatcher is read-only, so this preserves the no-game-state-write rule.
T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
t = rep(t,
'''use super::hook::{live_pass_should_finish, live_pass_telemetry};\n''',
'''use super::hook::{live_pass_observe_hjoypad_down, live_pass_should_finish, live_pass_telemetry};\n''',
        'trace observer import')

needle = '''        self.len += 1;\n\n        // v7.6.7 stops only after the 2F pass and four remasked frames.\n'''
replacement = '''        self.len += 1;\n\n        // Game-side validation: FF9A is Crystal hJoypadDown.  This records\n        // whether UP really reached the game, rather than trusting host mask\n        // bookkeeping alone.\n        live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));\n\n        // v7.6.7 stops only after the 2F pass and four remasked frames.\n'''
t = rep(t, needle, replacement, 'trace FF9A observer')

# Extend existing LIVEPASS CSV.  Append fields at the end to avoid disturbing
# the already audited 26-value core telemetry.
old_header = 'first_remask_advance,first_remask_tick,first_remask_mcycle,first_remask_pc\\nLIVEPASS,V767,'
new_header = 'first_remask_advance,first_remask_tick,first_remask_mcycle,first_remask_pc,game_observed_advances,game_mask_up_advances,game_pass_up_advances,game_remask_up_advances,game_first_mask_hjoy,game_first_pass_hjoy,game_first_remask_hjoy\\nLIVEPASS,V767B,'
if t.count(old_header) != 1:
    raise SystemExit(f'v767b CSV header count {t.count(old_header)}')
t = t.replace(old_header, new_header, 1)

old_fmt = '{},{},{:02X},{:04X}\\n",\n            lp.armed_advance,'
new_fmt = '{},{},{:02X},{:04X},{},{},{},{},{:02X},{:02X},{:02X}\\n",\n            lp.armed_advance,'
if t.count(old_fmt) != 1:
    raise SystemExit(f'v767b CSV format tail count {t.count(old_fmt)}')
t = t.replace(old_fmt, new_fmt, 1)

old_args = '''            lp.first_remask_mcycle,\n            lp.first_remask_pc\n        );\n'''
new_args = '''            lp.first_remask_mcycle,\n            lp.first_remask_pc,\n            lp.game_observed_advances,\n            lp.game_mask_up_advances,\n            lp.game_pass_up_advances,\n            lp.game_remask_up_advances,\n            lp.game_first_mask_hjoy,\n            lp.game_first_pass_hjoy,\n            lp.game_first_remask_hjoy\n        );\n'''
t = rep(t, old_args, new_args, 'CSV game args')
T.write_text(t)

print('Applied v7.6.7b: compile declaration + dual-view HID checks + FF9A game-side UP telemetry')
