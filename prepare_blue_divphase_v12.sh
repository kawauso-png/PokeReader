#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
CTRACE=3gx/sources/blue_dvtrace.c

if ! grep -q '^mod phase_tracker;$' "$RUST"; then
    sed -i '1imod phase_tracker;' "$RUST"
fi
if ! grep -q '^mod k_observer;$' "$RUST"; then
    sed -i '1imod k_observer;' "$RUST"
fi

if ! grep -q 'host_blue_phase_tracker_append_csv' "$RUST"; then
    awk '
    { print }
    /fn host_blue_gbrelease_valid\(\) -> u32;/ {
        print "    fn host_blue_phase_tracker_append_csv(slot: u32, transitions: u32, fits: u32, subs: u32, lock_prefix: u32, forecast_checks: u32, forecast_hits: u32, resets: u32) -> u32;"
        print "    fn host_blue_kobserver_append_csv(slot: u32, rows: *const k_observer::KObsRow, count: u32, valid_total: u32, invalid_total: u32) -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'k_observer::mark_arm();' "$RUST"; then
    awk '
    /RUN_STATE.fixed_target = Some\(s\);/ {
        print "            phase_tracker::mark_arm();"
        print "            k_observer::mark_arm();"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'k_observer::observe' "$RUST"; then
    awk '
    { print }
    /state.last_snapshot = current;/ {
        print "        let phase_usable = current.all_ptrs_ok() && !current.in_mewtwo_battle();"
        print "        let _ = phase_tracker::observe("
        print "            previous.seq, previous.rng, previous.div,"
        print "            current.seq, current.rng, current.div, phase_usable,"
        print "        );"
        print "        if phase_usable {"
        print "            k_observer::observe("
        print "                previous.seq, previous.rng, previous.div,"
        print "                current.seq, current.rng, current.div,"
        print "            );"
        print "        }"
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
            print "                        slot, arm_phase.transitions as u32, arm_phase.fits as u32,"
            print "                        arm_phase.sub_count as u32, arm_phase.lock_prefix as u32,"
            print "                        arm_phase.forecast_checks as u32, arm_phase.forecast_hits as u32,"
            print "                        arm_phase.resets as u32,"
            print "                    );"
            print "                }"
            print "                let k_count = k_observer::arm_count();"
            print "                if slot != 0 && k_count != 0 {"
            print "                    let _ = host_blue_kobserver_append_csv("
            print "                        slot, k_observer::arm_rows_ptr(), k_count,"
            print "                        k_observer::arm_valid_total(), k_observer::arm_invalid_total(),"
            print "                    );"
            print "                }"
        }
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'KOBS N{} U{} M' "$RUST"; then
    awk '
    /if let Some\(result\) = state.result \{/ {
        print "        let phase_live = phase_tracker::stats();"
        print "        let phase_arm = phase_tracker::arm_stats();"
        print "        let phase_show = if phase_arm.valid { phase_arm } else { phase_live };"
        print "        let kobs = k_observer::stats();"
        print "        pnp::println!(\"PH T{} F{} S{}\", phase_show.transitions, phase_show.fits, phase_show.sub_count);"
        print "        pnp::println!(\"OBS K{:02X} D{:02X} G{}\", phase_show.last_k, phase_show.last_div_step, phase_show.last_gap);"
        print "        pnp::println!(\"KOBS N{} U{} M{:02X} {}%\", kobs.valid_total, kobs.unique, kobs.mode_k, kobs.mode_pct);"
        print "        pnp::println!(\"K4 {:02X}/{:02X}/{:02X}/{:02X}\", kobs.phase_mode[0], kobs.phase_mode[1], kobs.phase_mode[2], kobs.phase_mode[3]);"
        print "        pnp::println!(\"KC {}/{}/{}/{}\", kobs.phase_pct[0], kobs.phase_pct[1], kobs.phase_pct[2], kobs.phase_pct[3]);"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE MEWTWO RNG v7.3.2 SAFE/BLUE MEWTWO RNG v7.4.3 KOBS/' "$RUST"
sed -i 's/PRED LOCKED: phase learn/K OBSERVER READ-ONLY/' "$RUST"

sed -i 's/phase_probe_begin(trigger_entry.div);/phase_probe_reset();/' "$CTRACE"
sed -i 's/^[[:space:]]*write_phase_probe(file, &off);/    \/\* v15: memory probe retired; K observer is Rust-only. \*\//g' "$CTRACE"
