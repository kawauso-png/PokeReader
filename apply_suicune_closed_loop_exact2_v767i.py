from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767i {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.7i fixes the v7.6.7h Exact2 trigger only.  FFA8 hJoyDown is a
# game-level value and can remain stale across the transition stop.  FFA4
# hJoypadDown is the low-level per-poll held state and is therefore the correct
# authority for counting the two physical-UP polling frames.  No input value is
# written or synthesized; FFA8 remains recorded for diagnostics.

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()
old = '''        let hjoy = joy[JOY_HJOY_DOWN];
        let up = (hjoy & PAD_UP) != 0;

        // Count distinct RNG advances where Crystal itself reports UP held.
        if up {
            if LIVE_PASS.exact2_up_advances == 0 || LIVE_PASS.exact2_last_up_advance != now {
                LIVE_PASS.exact2_last_up_advance = now;
                LIVE_PASS.exact2_up_advances = LIVE_PASS.exact2_up_advances.saturating_add(1);
                if LIVE_PASS.exact2_up_advances == 1 {
                    LIVE_PASS.exact2_first_up_advance = now;
                } else if LIVE_PASS.exact2_up_advances == 2 {
                    LIVE_PASS.exact2_second_up_advance = now;
                    LIVE_PASS.exact2_pause_requested = 1;
                    EXACT2_RELEASE_WAITING = true;
                    pnp::request_pause();
                }
            }
        } else if LIVE_PASS.exact2_release_confirmed != 0 && LIVE_PASS.exact2_first_clear_advance == 0 {
            LIVE_PASS.exact2_first_clear_advance = now;
        }
'''
new = '''        let hjoy = joy[JOY_HJOY_DOWN];
        let up = (hjoy & PAD_UP) != 0; // game-level diagnostic only (FFA8)
        let low_up = (joy[JOY_HJOYPAD_DOWN] & PAD_UP) != 0; // FFA4 poll authority

        // Count distinct RNG advances where Crystal's low-level joypad poll
        // itself reports UP held.  Unlike FFA8, FFA4 is not treated as an
        // accepted-frame counter across game-level transition stalls.
        if low_up {
            if LIVE_PASS.exact2_up_advances == 0 || LIVE_PASS.exact2_last_up_advance != now {
                LIVE_PASS.exact2_last_up_advance = now;
                LIVE_PASS.exact2_up_advances = LIVE_PASS.exact2_up_advances.saturating_add(1);
                if LIVE_PASS.exact2_up_advances == 1 {
                    LIVE_PASS.exact2_first_up_advance = now;
                } else if LIVE_PASS.exact2_up_advances == 2 {
                    LIVE_PASS.exact2_second_up_advance = now;
                    LIVE_PASS.exact2_pause_requested = 1;
                    EXACT2_RELEASE_WAITING = true;
                    pnp::request_pause();
                }
            }
        } else if LIVE_PASS.exact2_release_confirmed != 0 && LIVE_PASS.exact2_first_clear_advance == 0 {
            LIVE_PASS.exact2_first_clear_advance = now;
        }
'''
h = rep(h, old, new, 'FFA4 Exact2 authority')
H.write_text(h)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
if t.count('V767H') < 5:
    raise SystemExit(f'v767i lineage markers too few: {t.count("V767H")}')
t = t.replace('V767H', 'V767I')
t = t.replace('exact2,version,accepted_up_advances,first_up_advance,second_up_advance,pause_requested,release_confirmed,first_clear_after_release',
              'exact2,version,polled_up_advances,first_up_advance,second_up_advance,pause_requested,release_confirmed,first_clear_after_release')
T.write_text(t)

print('Applied v7.6.7i: Exact2 authority = JP FFA4 hJoypadDown low-level poll')
