#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
CTRACE=3gx/sources/blue_dvtrace.c

# Experimental branch integration is kept as a deterministic build-time patch
# so the proven v7.3.7 control path stays byte-for-byte reviewable in Git.
if ! grep -q '^mod phase_tracker;$' "$RUST"; then
    sed -i '1imod phase_tracker;' "$RUST"
fi

if ! grep -q 'host_blue_phase_tracker_append_csv' "$RUST"; then
    awk '
    { print }
    /fn host_blue_gbrelease_valid\(\) -> u32;/ {
        print "    fn host_blue_phase_tracker_append_csv(slot: u32, transitions: u32, fits: u32, subs: u32, lock_prefix: u32, forecast_checks: u32, forecast_hits: u32, resets: u32) -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'phase_tracker::mark_arm();' "$RUST"; then
    awk '
    /RUN_STATE.fixed_target = Some\(s\);/ {
        print "            phase_tracker::mark_arm();"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'phase_clean = !current.in_mewtwo_battle' "$RUST"; then
    awk '
    { print }
    /state.last_snapshot = current;/ {
        print "        let (phase_joy_pressed, phase_joy_held) = pnp::blue_game_joy();"
        print "        let phase_clean = !current.in_mewtwo_battle()"
        print "            && !pnp::is_pressing(0x00FFu32)"
        print "            && phase_joy_pressed == 0"
        print "            && phase_joy_held == 0;"
        print "        let _ = phase_tracker::observe("
        print "            previous.seq, previous.rng, previous.div,"
        print "            current.seq, current.rng, current.div, phase_clean,"
        print "        );"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'arm_phase = phase_tracker::arm_stats' "$RUST"; then
    awk '
    BEGIN { slot_seen = 0 }
    { print }
    /let slot = host_blue_dvtrace_save_slot\(\);/ {
        slot_seen++
        if (slot_seen == 1) {
            print "                let arm_phase = phase_tracker::arm_stats();"
            print "                if slot != 0 && arm_phase.valid {"
            print "                    let _ = host_blue_phase_tracker_append_csv("
            print "                        slot,"
            print "                        arm_phase.transitions as u32,"
            print "                        arm_phase.fits as u32,"
            print "                        arm_phase.sub_count as u32,"
            print "                        arm_phase.lock_prefix as u32,"
            print "                        arm_phase.forecast_checks as u32,"
            print "                        arm_phase.forecast_hits as u32,"
            print "                        arm_phase.resets as u32,"
            print "                    );"
            print "                }"
        }
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'PH T{} F{} S{}' "$RUST"; then
    awk '
    /if let Some\(result\) = state.result \{/ {
        print "        let phase_live = phase_tracker::stats();"
        print "        let phase_arm = phase_tracker::arm_stats();"
        print "        let phase_show = if phase_arm.valid { phase_arm } else { phase_live };"
        print "        pnp::println!(\"PH T{} F{} S{}\", phase_show.transitions, phase_show.fits, phase_show.sub_count);"
        print "        pnp::println!(\"LOCK {}F V{}/{}\", phase_show.lock_prefix, phase_show.forecast_hits, phase_show.forecast_checks);"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE MEWTWO RNG v7.3.2 SAFE/BLUE MEWTWO RNG v7.4.0 DIVPHASE/' "$RUST"
sed -i 's/PRED LOCKED: phase learn/DIVPHASE READ-ONLY/' "$RUST"

# Retire the 1 KiB discovery scan from v7.3.7. The old trace fields remain for
# CSV compatibility, but no probe snapshot or PHASE table is produced in v12.
sed -i 's/phase_probe_begin(trigger_entry.div);/phase_probe_reset();/' "$CTRACE"
sed -i 's/^[[:space:]]*write_phase_probe(file, &off);/    \/\* v12: bounded memory probe retired; DIV phase tracker is Rust-only. \*\//g' "$CTRACE"
