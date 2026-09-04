from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767g {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.7g returns to the v7.6.7d hook-timed mask/pass path, but replaces the
# incorrect FF9A verifier with the JP VC Crystal joypad chain FFA2..FFA9.
# It records host key state and all eight joypad bytes once per advance.
# The 16/2/4 timing is intentionally unchanged so this run measures how the
# existing 2-advance unmask window lands on Crystal's actual poll chain.

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

h = rep(h,
'''const LIVE_POST_FRAMES: u32 = 4;
const RJOYP_ADDR: u32 = 0xff00;''',
'''const LIVE_POST_FRAMES: u32 = 4;
const LIVE_SAMPLE_CAP: usize = 22;
const JOY_HJOY_DOWN: usize = 6; // FFA8
const RJOYP_ADDR: u32 = 0xff00;''',
'joy constants')

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
    pub joy_sample_count: u8,
    pub joy_sample_rel: [u8; LIVE_SAMPLE_CAP],
    pub joy_sample_host: [u32; LIVE_SAMPLE_CAP],
    pub joy_samples: [[u8; 8]; LIVE_SAMPLE_CAP],
    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
}''',
'telemetry fields')

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
        joy_sample_count: 0,
        joy_sample_rel: [0; LIVE_SAMPLE_CAP],
        joy_sample_host: [0; LIVE_SAMPLE_CAP],
        joy_samples: [[0; 8]; LIVE_SAMPLE_CAP],
        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
    };''',
'telemetry defaults')

h = rep(h,
'''/// Read-only proof of what Crystal itself decoded from rJOYP.
pub fn live_pass_observe_hjoypad_down(hjoy: u8) {
    const PAD_UP: u8 = 0x40;''',
'''/// Read-only JP VC Crystal joypad chain during the hook-timed mask/pass test.
/// FFA2..FFA9: Released, Pressed, Down, Sum, JoyReleased, JoyPressed, JoyDown, JoyLast.
pub fn live_pass_observe_joymap(joy: [u8; 8], host_keys: u32) {
    const PAD_UP: u8 = 0x40;
    const HOST_UP: u32 = 0x40;''',
'observer signature')

h = rep(h,
'''        LIVE_PASS.game_last_observed_advance = now;
        LIVE_PASS.game_observed_advances = LIVE_PASS.game_observed_advances.saturating_add(1);

        let before_pass =''',
'''        LIVE_PASS.game_last_observed_advance = now;
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

        let sample_idx = LIVE_PASS.joy_sample_count as usize;
        if sample_idx < LIVE_SAMPLE_CAP {
            let rel = now.wrapping_sub(LIVE_PASS.first_input_advance) as u8;
            LIVE_PASS.joy_sample_rel[sample_idx] = rel;
            LIVE_PASS.joy_sample_host[sample_idx] = host_keys;
            LIVE_PASS.joy_samples[sample_idx] = joy;
            LIVE_PASS.joy_sample_count = LIVE_PASS.joy_sample_count.saturating_add(1);
            for i in 0..8 {
                if (joy[i] & PAD_UP) != 0 {
                    LIVE_PASS.joy_up_counts[i] = LIVE_PASS.joy_up_counts[i].saturating_add(1);
                    if LIVE_PASS.joy_first_up_rel[i] == 0xff {
                        LIVE_PASS.joy_first_up_rel[i] = rel;
                    }
                }
            }
        }

        let before_pass =''',
'host/raw observation')

h = rep(h,
'''        let up = (hjoy & PAD_UP) != 0;

        if before_pass {''',
'''        let hjoy = joy[JOY_HJOY_DOWN];
        let up = (hjoy & PAD_UP) != 0;

        if before_pass {''',
'authoritative FFA8')
H.write_text(h)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
t = rep(t,
'use super::hook::{live_pass_observe_hjoypad_down, live_pass_should_finish, live_pass_telemetry};',
'use super::hook::{live_pass_observe_joymap, live_pass_should_finish, live_pass_telemetry};',
'trace import')

t = rep(t,
'''        // Read-only game-side verification: Crystal hJoypadDown (FF9A).
        live_pass_observe_hjoypad_down(gb_mem::read_u8(0xff9a));''',
'''        // v7.6.7g: JP VC Crystal joypad chain while v7.6.7d masking is active.
        let joymap = [
            gb_mem::read_u8(0xffa2), gb_mem::read_u8(0xffa3),
            gb_mem::read_u8(0xffa4), gb_mem::read_u8(0xffa5),
            gb_mem::read_u8(0xffa6), gb_mem::read_u8(0xffa7),
            gb_mem::read_u8(0xffa8), gb_mem::read_u8(0xffa9),
        ];
        live_pass_observe_joymap(joymap, pnp::current_keys());''',
'correct joymap call')

t = rep(t, 'LIVEPASS,V767D,', 'LIVEPASS,V767G,', 'main lineage')

t = rep(t,
'''        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();''',
'''        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "\\nlive_pass_host,version,host_observed_advances,host_up_advances,host_first_keys\\nLIVEPASSHOST,V767G,{},{},{:08X}\\n",
            lp.host_observed_advances,
            lp.host_up_advances,
            lp.host_first_keys
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(
            line,
            "\\njoymap,version,samples,ffa2_up,ffa3_up,ffa4_up,ffa5_up,ffa6_up,ffa7_up,ffa8_up,ffa9_up,ffa2_first_rel,ffa3_first_rel,ffa4_first_rel,ffa5_first_rel,ffa6_first_rel,ffa7_first_rel,ffa8_first_rel,ffa9_first_rel\\nJOYMAP,V767G,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\\n",
            lp.joy_sample_count,
            lp.joy_up_counts[0], lp.joy_up_counts[1], lp.joy_up_counts[2], lp.joy_up_counts[3],
            lp.joy_up_counts[4], lp.joy_up_counts[5], lp.joy_up_counts[6], lp.joy_up_counts[7],
            lp.joy_first_up_rel[0], lp.joy_first_up_rel[1], lp.joy_first_up_rel[2], lp.joy_first_up_rel[3],
            lp.joy_first_up_rel[4], lp.joy_first_up_rel[5], lp.joy_first_up_rel[6], lp.joy_first_up_rel[7]
        );
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(line, "\\njoy_frames,version,index,rel_advance,host_keys,ffa2,ffa3,ffa4,ffa5,ffa6,ffa7,ffa8,ffa9\\n");
        pnp::trace_file_write(line.as_bytes());
        let n = lp.joy_sample_count as usize;
        for i in 0..n.min(22) {
            line.clear();
            let j = lp.joy_samples[i];
            let _ = write!(
                line,
                "JOYFRAME,V767G,{},{},{:08X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X}\\n",
                i, lp.joy_sample_rel[i], lp.joy_sample_host[i],
                j[0], j[1], j[2], j[3], j[4], j[5], j[6], j[7]
            );
            pnp::trace_file_write(line.as_bytes());
        }

        pnp::trace_file_close();''',
'host/joy CSV export')
T.write_text(t)

print('Applied v7.6.7g: v767d mask/pass + JP joypad chain FFA2-FFA9')
