from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767e {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.7e is a read-only baseline. v7.6.7d showed that the 16/2/4 timing
# windows were exact but Crystal FF9A saw no UP even in the 2F pass window.
# Before moving the mask earlier/later, prove whether continuous resume with
# physical UP held reaches Crystal at all. No HID word is modified in this
# version. Host key state and Crystal hJoypadDown are observed side by side.

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

# Host-side observation fields. These are sampled once per RNG advance from
# the same Trace::record call that reads Crystal FF9A.
h = rep(h,
'''    pub game_first_remask_hjoy: u8,
    pub game_last_observed_advance: u32,
}''',
'''    pub game_first_remask_hjoy: u8,
    pub game_last_observed_advance: u32,
    pub host_observed_advances: u8,
    pub host_up_advances: u8,
    pub host_first_keys: u32,
    pub host_last_observed_advance: u32,
}''', 'host telemetry fields')

h = rep(h,
'''        game_first_remask_hjoy: 0xff,
        game_last_observed_advance: 0,
    };''',
'''        game_first_remask_hjoy: 0xff,
        game_last_observed_advance: 0,
        host_observed_advances: 0,
        host_up_advances: 0,
        host_first_keys: 0,
        host_last_observed_advance: 0,
    };''', 'host telemetry defaults')

# Baseline must not touch HID at ARM time either. It only needs the existing
# continuous-run state machine and exact +17/+19/+22 windows.
h = rep(h,
'''    // There must be no transient mask left from an earlier aborted trial.
    let restored = pnp::hid_mask_up_restore();
    let capable = restored && pnp::hid_mask_capable();
    let (begin_base, restore_base) = pnp::hid_mask_stats();''',
'''    // v7.6.7e baseline: observation only, no HID restore/capability write path.
    let capable = true;
    let (begin_base, restore_base) = pnp::hid_mask_stats();''', 'read-only arm')

# Extend the authoritative once-per-advance observer with host key state.
h = rep(h,
        'pub fn live_pass_observe_hjoypad_down(hjoy: u8) {\n    const PAD_UP: u8 = 0x40;',
        'pub fn live_pass_observe_hjoypad_down(hjoy: u8, host_keys: u32) {\n    const PAD_UP: u8 = 0x40;\n    const HOST_UP: u32 = 0x40;',
        'observer signature')

needle = '''        LIVE_PASS.game_last_observed_advance = now;
        LIVE_PASS.game_observed_advances = LIVE_PASS.game_observed_advances.saturating_add(1);

        let before_pass ='''
replacement = '''        LIVE_PASS.game_last_observed_advance = now;
        LIVE_PASS.game_observed_advances = LIVE_PASS.game_observed_advances.saturating_add(1);

        if LIVE_PASS.host_observed_advances == 0 {
            LIVE_PASS.host_first_keys = host_keys;
        }
        if LIVE_PASS.host_last_observed_advance != now {
            LIVE_PASS.host_last_observed_advance = now;
            LIVE_PASS.host_observed_advances = LIVE_PASS.host_observed_advances.saturating_add(1);
            if (host_keys & HOST_UP) != 0 {
                LIVE_PASS.host_up_advances = LIVE_PASS.host_up_advances.saturating_add(1);
            }
        }

        let before_pass ='''
h = rep(h, needle, replacement, 'host observation accounting')

# Make the previous-mask restore helper a true no-op. This guarantees the live
# path cannot write to the producer-owned HID shared word.
start = h.index('fn live_pass_restore_previous_mask() {')
end = h.index('\n}\n\nfn live_pass_filter_rjoy', start) + 2
h = h[:start] + '''fn live_pass_restore_previous_mask() {
    // v7.6.7e: no-mask baseline; intentionally no HID write.
}''' + h[end:]

# Retain all rJOYP/window/phase accounting, but remove the mask begin at the end
# of non-pass reads. Thus UP is never hidden in any of the 22 observed frames.
old_mask_tail = '''
    if !pnp::hid_mask_up_begin() {
        unsafe { LIVE_PASS_ARMED = false; }
        pnp::request_pause();
    }
}'''
new_mask_tail = '''
    // v7.6.7e: no-mask baseline. Do not modify HID here.
}'''
if h.count(old_mask_tail) != 1:
    raise SystemExit(f'v767e live mask tail count {h.count(old_mask_tail)}')
h = h.replace(old_mask_tail, new_mask_tail, 1)
H.write_text(h)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
t = rep(t,
        'live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));',
        'live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a), pnp::current_keys());',
        'host+game observer call')
t = rep(t, 'LIVEPASS,V767D,', 'LIVEPASS,V767E,', 'CSV lineage')

# Add a separate compact host-input line rather than changing the already
# validated 38-column LIVEPASS layout.
anchor = '        pnp::trace_file_write(line.as_bytes());\n\n        pnp::trace_file_close();'
insert = '''        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "\\nlive_pass_host,version,host_observed_advances,host_up_advances,host_first_keys\\nLIVEPASSHOST,V767E,{},{},{:08X}\\n",
            lp.host_observed_advances,
            lp.host_up_advances,
            lp.host_first_keys
        );
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();'''
t = rep(t, anchor, insert, 'host CSV line')
T.write_text(t)

print('Applied v7.6.7e: no HID masking; host UP + Crystal FF9A baseline')
