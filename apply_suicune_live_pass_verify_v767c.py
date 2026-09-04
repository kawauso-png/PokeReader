from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767c {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


# C-side verification.
P = Path('3gx/sources/hid.c')
c = P.read_text()
c = rep(c, '#include <3ds.h>\n#include "common.h"\n',
        '#include <3ds.h>\n#include "csvc.h"\n#include "common.h"\n',
        'csvc declaration include')
c = rep(c, 'if ((*pa & KEY_DUP) != 0)',
        'if (((*pa | *g_key_addr) & KEY_DUP) != 0)',
        'mask dual-view condition')
c = rep(c, 'if (*pa != saved)',
        'if (*pa != saved || *g_key_addr != saved)',
        'restore dual-view condition')

# Fail closed on a sequencing fault. A second begin while a previous mask is
# still active must never be silently accepted as a valid trial. Restore the
# exact old word with dual-view verification, mark begin failure, and abort the
# new mask. The next Rust hook will pause the trial.
c = rep(c,
'''  // Never stack masks. Restore the previous exact word first.
  if (g_up_mask_active)
  {
    vu32 *old_pa = (vu32 *)PA_FROM_VA_PTR(g_key_addr);
    *old_pa = g_up_mask_saved;
    g_up_mask_active = false;
  }
''',
'''  // Stacking is a sequencing fault. Restore exactly, verify, and fail this
  // begin so a broken hook order can never masquerade as a valid timing run.
  if (g_up_mask_active)
  {
    if (g_key_addr == 0)
    {
      g_up_mask_restore_failures++;
      g_up_mask_begin_failures++;
      return 0;
    }
    vu32 *old_pa = (vu32 *)PA_FROM_VA_PTR(g_key_addr);
    u32 old_saved = g_up_mask_saved;
    *old_pa = old_saved;
    if (*old_pa != old_saved || *g_key_addr != old_saved)
    {
      g_up_mask_restore_failures++;
      g_up_mask_begin_failures++;
      return 0;
    }
    g_up_mask_active = false;
    g_up_mask_begin_failures++;
    return 0;
  }
''', 'stacking fail closed')

# If a mask write fails verification, restoration of the original word must
# also be verified. If restoration itself fails, keep active=true so later
# restore calls continue retrying rather than forgetting an uncertain mask.
c = rep(c,
'''  if (((*pa | *g_key_addr) & KEY_DUP) != 0)
  {
    g_up_mask_begin_failures++;
    *pa = original;
      return 0;
  }
''',
'''  if (((*pa | *g_key_addr) & KEY_DUP) != 0)
  {
    g_up_mask_begin_failures++;
    *pa = original;
    if (*pa != original || *g_key_addr != original)
    {
      g_up_mask_restore_failures++;
      g_up_mask_saved = original;
      g_up_mask_active = true;
    }
    return 0;
  }
''', 'failed-mask restoration verification')

c = rep(c,
'''  if (g_key_addr == 0)
  {
    g_up_mask_restore_failures++;
    g_up_mask_active = false;
    return 0;
  }
''',
'''  if (g_key_addr == 0)
  {
    // Preserve active=true: the exact saved word is still pending restore.
    g_up_mask_restore_failures++;
    return 0;
  }
''', 'restore null-address retryability')

c = rep(c,
'''  u32 saved = g_up_mask_saved;
  *pa = saved;
  g_up_mask_active = false;

  if (*pa != saved || *g_key_addr != saved)
  {
    g_up_mask_restore_failures++;
    return 0;
  }
  return 1;
''',
'''  u32 saved = g_up_mask_saved;
  *pa = saved;

  if (*pa != saved || *g_key_addr != saved)
  {
    // Keep active=true so the next hook/plugin scan retries exact restore.
    g_up_mask_restore_failures++;
    return 0;
  }
  g_up_mask_active = false;
  return 1;
''', 'restore active cleared only after verification')
P.write_text(c)

# Rust hook telemetry: observe Crystal's own hJoypadDown (FF9A) after each
# presented frame. Observation only; no GB RAM writes.
H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()
h = rep(h, '    pub first_remask_pc: u16,\n}',
'''    pub first_remask_pc: u16,
    pub game_observed_advances: u8,
    pub game_mask_observed_advances: u8,
    pub game_pass_observed_advances: u8,
    pub game_remask_observed_advances: u8,
    pub game_mask_up_advances: u8,
    pub game_pass_up_advances: u8,
    pub game_remask_up_advances: u8,
    pub game_first_mask_hjoy: u8,
    pub game_first_pass_hjoy: u8,
    pub game_first_remask_hjoy: u8,
    pub game_last_observed_advance: u32,
}''', 'telemetry game fields')

h = rep(h, '        first_remask_pc: 0,\n    };',
'''        first_remask_pc: 0,
        game_observed_advances: 0,
        game_mask_observed_advances: 0,
        game_pass_observed_advances: 0,
        game_remask_observed_advances: 0,
        game_mask_up_advances: 0,
        game_pass_up_advances: 0,
        game_remask_up_advances: 0,
        game_first_mask_hjoy: 0xff,
        game_first_pass_hjoy: 0xff,
        game_first_remask_hjoy: 0xff,
        game_last_observed_advance: 0,
    };''', 'telemetry game defaults')

# Failure counters are global C telemetry. Snapshot them at ARM so the CSV
# reports failures from this trial only, rather than failures from plugin boot.
h = rep(h,
'''static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;
''',
'''static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;
static mut LIVE_PASS_BEGIN_FAILURE_BASE: u16 = 0;
static mut LIVE_PASS_RESTORE_FAILURE_BASE: u16 = 0;
''', 'per-trial failure baselines')

h = rep(h,
'''    let capable = restored && pnp::hid_mask_capable();
    let base = rng_advance();
    unsafe {
        LIVE_PASS = LivePassTelemetry {
''',
'''    let capable = restored && pnp::hid_mask_capable();
    let (begin_base, restore_base) = pnp::hid_mask_stats();
    let base = rng_advance();
    unsafe {
        LIVE_PASS_BEGIN_FAILURE_BASE = begin_base;
        LIVE_PASS_RESTORE_FAILURE_BASE = restore_base;
        LIVE_PASS = LivePassTelemetry {
''', 'capture failure baselines at arm')

h = rep(h, '        out.begin_failures = bf;\n        out.restore_failures = rf;',
'''        out.begin_failures = bf.wrapping_sub(LIVE_PASS_BEGIN_FAILURE_BASE);
        out.restore_failures = rf.wrapping_sub(LIVE_PASS_RESTORE_FAILURE_BASE);''',
        'per-trial failure deltas')

# pass_end_advance is the first remasked advance. Four completed remask frames
# are pass_end..pass_end+3, so stop on +3 rather than running a fifth frame.
h = rep(h,
        '        let finish = LIVE_PASS.pass_end_advance.wrapping_add(LIVE_POST_FRAMES);',
        '        let finish = LIVE_PASS.pass_end_advance.wrapping_add(LIVE_POST_FRAMES - 1);',
        'four-frame remask stop boundary')

anchor = 'pub fn live_pass_should_finish() -> bool {'
if h.count(anchor) != 1:
    raise SystemExit(f'v767c live finish anchor count {h.count(anchor)}')
observe = r'''/// Read-only proof of what Crystal itself decoded from rJOYP.
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
            LIVE_PASS.game_mask_observed_advances = LIVE_PASS.game_mask_observed_advances.saturating_add(1);
            if LIVE_PASS.game_first_mask_hjoy == 0xff {
                LIVE_PASS.game_first_mask_hjoy = hjoy;
            }
            if up {
                LIVE_PASS.game_mask_up_advances = LIVE_PASS.game_mask_up_advances.saturating_add(1);
            }
        } else if in_pass {
            LIVE_PASS.game_pass_observed_advances = LIVE_PASS.game_pass_observed_advances.saturating_add(1);
            if LIVE_PASS.game_first_pass_hjoy == 0xff {
                LIVE_PASS.game_first_pass_hjoy = hjoy;
            }
            if up {
                LIVE_PASS.game_pass_up_advances = LIVE_PASS.game_pass_up_advances.saturating_add(1);
            }
        } else if after_pass {
            LIVE_PASS.game_remask_observed_advances = LIVE_PASS.game_remask_observed_advances.saturating_add(1);
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

# Trace-side game input observation.
T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
t = rep(t,
        'use super::hook::{live_pass_should_finish, live_pass_telemetry};',
        'use super::hook::{live_pass_observe_hjoypad_down, live_pass_should_finish, live_pass_telemetry};',
        'trace observer import')

marker = '        // v7.6.7 stops only after the 2F pass and four remasked frames.'
pos = t.find(marker)
if pos < 0:
    raise SystemExit('v767c auto-stop marker not found')
obs = '''        // Read-only game-side verification: Crystal hJoypadDown (FF9A).\n        live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));\n\n'''
t = t[:pos] + obs + t[pos:]

# Extend LIVEPASS CSV by editing only the unique tail/header tokens.
old_header = 'first_remask_advance,first_remask_tick,first_remask_mcycle,first_remask_pc\\nLIVEPASS,V767,'
new_header = 'first_remask_advance,first_remask_tick,first_remask_mcycle,first_remask_pc,game_observed_advances,game_mask_observed_advances,game_pass_observed_advances,game_remask_observed_advances,game_mask_up_advances,game_pass_up_advances,game_remask_up_advances,game_first_mask_hjoy,game_first_pass_hjoy,game_first_remask_hjoy\\nLIVEPASS,V767C,'
t = rep(t, old_header, new_header, 'CSV header')

old_tail = '{},{},{:02X},{:04X}\\n",\n            lp.armed_advance,'
new_tail = '{},{},{:02X},{:04X},{},{},{},{},{},{},{},{:02X},{:02X},{:02X}\\n",\n            lp.armed_advance,'
t = rep(t, old_tail, new_tail, 'CSV format tail')

old_args = '            lp.first_remask_mcycle,\n            lp.first_remask_pc\n        );'
new_args = '''            lp.first_remask_mcycle,
            lp.first_remask_pc,
            lp.game_observed_advances,
            lp.game_mask_observed_advances,
            lp.game_pass_observed_advances,
            lp.game_remask_observed_advances,
            lp.game_mask_up_advances,
            lp.game_pass_up_advances,
            lp.game_remask_up_advances,
            lp.game_first_mask_hjoy,
            lp.game_first_pass_hjoy,
            lp.game_first_remask_hjoy
        );'''
t = rep(t, old_args, new_args, 'CSV game args')
T.write_text(t)

print('Applied v7.6.7c: exact 16/2/4 FF9A windows + retryable fail-closed HID restore telemetry')
