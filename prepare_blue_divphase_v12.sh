#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
KOBS=reader_core/src/gen1/k_observer.rs
CTRACE=3gx/sources/blue_dvtrace.c

for mod in phase_tracker k_observer boot_capture adaptive_model; do
    if ! grep -q "^mod ${mod};$" "$RUST"; then
        sed -i "1imod ${mod};" "$RUST"
    fi
done

if ! grep -q 'host_blue_bootcapture_append_csv' "$RUST"; then
    awk '
    { print }
    /fn host_blue_gbrelease_valid\(\) -> u32;/ {
        print "    fn host_blue_phase_tracker_append_csv(slot: u32, transitions: u32, fits: u32, subs: u32, lock_prefix: u32, forecast_checks: u32, forecast_hits: u32, resets: u32) -> u32;"
        print "    fn host_blue_kobserver_append_csv(slot: u32, rows: *const k_observer::KObsRow, count: u32, valid_total: u32, invalid_total: u32) -> u32;"
        print "    fn host_blue_bootcapture_append_csv(slot: u32, rows: *const boot_capture::BootRow, count: u32, valid_total: u32, invalid_total: u32) -> u32;"
        print "    fn host_blue_adaptive_append_csv(slot: u32, ready: u32, clean_tail: u32, base: u32, base_hits: u32, residue20: u32, marker_hits: u32, marker_total: u32, core_hits: u32, core_total: u32, sub_count: u32, div_lock: u32) -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi
if ! grep -q 'host_blue_adaptive_append_csv' "$RUST"; then
    awk '
    { print }
    /fn host_blue_gbrelease_valid\(\) -> u32;/ {
        print "    fn host_blue_adaptive_append_csv(slot: u32, ready: u32, clean_tail: u32, base: u32, base_hits: u32, residue20: u32, marker_hits: u32, marker_total: u32, core_hits: u32, core_total: u32, sub_count: u32, div_lock: u32) -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'boot_capture::mark_arm();' "$RUST"; then
    awk '
    /RUN_STATE.fixed_target = Some\(s\);/ {
        print "            phase_tracker::mark_arm();"
        print "            k_observer::mark_arm();"
        print "            boot_capture::mark_arm();"
        print "            adaptive_model::mark_arm();"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi
if ! grep -q 'adaptive_model::mark_arm();' "$RUST"; then
    awk '
    /boot_capture::mark_arm\(\);/ { print; print "            adaptive_model::mark_arm();"; next }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'boot_capture::observe' "$RUST"; then
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
        print "        let _ = boot_capture::observe("
        print "            previous.seq, previous.rng, previous.div,"
        print "            current.seq, current.rng, current.div, current.status,"
        print "        );"
        print "        let _ = adaptive_model::observe("
        print "            previous.seq, previous.rng, previous.div,"
        print "            current.seq, current.rng, current.div, phase_usable,"
        print "        );"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi
if ! grep -q 'adaptive_model::observe' "$RUST"; then
    awk '
    { print }
    /boot_capture::observe\(/ {
        seen=1
    }
    seen && /\);/ {
        print "        let _ = adaptive_model::observe("
        print "            previous.seq, previous.rng, previous.div,"
        print "            current.seq, current.rng, current.div, phase_usable,"
        print "        );"
        seen=0
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'boot_capture::arm_count' "$RUST"; then
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
            print "                let boot_count = boot_capture::arm_count();"
            print "                if slot != 0 && boot_count != 0 {"
            print "                    let _ = host_blue_bootcapture_append_csv("
            print "                        slot, boot_capture::arm_rows_ptr(), boot_count,"
            print "                        boot_capture::arm_valid(), boot_capture::arm_invalid(),"
            print "                    );"
            print "                }"
            print "                let adp = adaptive_model::arm_stats();"
            print "                if slot != 0 && adp.valid {"
            print "                    let _ = host_blue_adaptive_append_csv("
            print "                        slot, u32::from(adp.ready), adp.clean_tail as u32, adp.base as u32,"
            print "                        adp.base_hits as u32, adp.residue20 as u32,"
            print "                        adp.marker_hits as u32, adp.marker_total as u32,"
            print "                        adp.core_hits as u32, adp.core_total as u32,"
            print "                        adp.sub_count as u32, adp.div_lock as u32,"
            print "                    );"
            print "                }"
        }
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi
if ! grep -q 'adaptive_model::arm_stats' "$RUST"; then
    awk '
    { print }
    /boot_capture::arm_invalid\(\),/ {
        inboot=1
    }
    inboot && /\);/ {
        print "                let adp = adaptive_model::arm_stats();"
        print "                if slot != 0 && adp.valid {"
        print "                    let _ = host_blue_adaptive_append_csv("
        print "                        slot, u32::from(adp.ready), adp.clean_tail as u32, adp.base as u32,"
        print "                        adp.base_hits as u32, adp.residue20 as u32,"
        print "                        adp.marker_hits as u32, adp.marker_total as u32,"
        print "                        adp.core_hits as u32, adp.core_total as u32,"
        print "                        adp.sub_count as u32, adp.div_lock as u32,"
        print "                    );"
        print "                }"
        inboot=0
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'OMNI N{} V{} I{}' "$RUST"; then
    awk '
    /if let Some\(result\) = state.result \{/ {
        print "        let phase_live = phase_tracker::stats();"
        print "        let phase_arm = phase_tracker::arm_stats();"
        print "        let phase_show = if phase_arm.valid { phase_arm } else { phase_live };"
        print "        let kobs = k_observer::stats();"
        print "        let omni = boot_capture::stats();"
        print "        let adp = adaptive_model::stats();"
        print "        pnp::println!(\"PH T{} F{} S{}\", phase_show.transitions, phase_show.fits, phase_show.sub_count);"
        print "        pnp::println!(\"OBS K{:02X} D{:02X} G{}\", phase_show.last_k, phase_show.last_div_step, phase_show.last_gap);"
        print "        pnp::println!(\"KOBS N{} U{} M{:02X} {}%\", kobs.valid_total, kobs.unique, kobs.mode_k, kobs.mode_pct);"
        print "        pnp::println!(\"OMNI N{} V{} I{}\", omni.count, omni.valid, omni.invalid);"
        print "        pnp::println!(\"ADP {} B{:02X} R{:02}\", if adp.ready { \"OK\" } else { \"--\" }, adp.base, adp.residue20);"
        print "        pnp::println!(\"H{}/{} M{}/{} S{} D{}\", adp.core_hits, adp.core_total, adp.marker_hits, adp.marker_total, adp.sub_count, adp.div_lock);"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi
if ! grep -q 'ADP {} B' "$RUST"; then
    awk '
    /let omni = boot_capture::stats\(\);/ {
        print
        print "        let adp = adaptive_model::stats();"
        next
    }
    /pnp::println!\(\"LAST K/ {
        print "        pnp::println!(\"ADP {} B{:02X} R{:02}\", if adp.ready { \"OK\" } else { \"--\" }, adp.base, adp.residue20);"
        print "        pnp::println!(\"H{}/{} M{}/{} S{} D{}\", adp.core_hits, adp.core_total, adp.marker_hits, adp.marker_total, adp.sub_count, adp.div_lock);"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

# Rust requires address-of access to mutable static arrays to be explicitly unsafe.
sed -i 's/core::ptr::addr_of!(ARM_ROWS) as \*const KObsRow/unsafe { core::ptr::addr_of!(ARM_ROWS) as *const KObsRow }/' "$KOBS"

sed -i 's/BLUE MEWTWO RNG v7.3.2 SAFE/BLUE MEWTWO RNG v7.5.1 ADAPT/' "$RUST"
sed -i 's/PRED LOCKED: phase learn/ADAPTIVE ENVELOPE READ-ONLY/' "$RUST"

# Heavy memory probing stays retired.  Adaptive capture only reads values already sampled by SAFE trace.
sed -i 's/phase_probe_begin(trigger_entry.div);/phase_probe_reset();/' "$CTRACE"
sed -i 's/^[[:space:]]*write_phase_probe(file, &off);/    \/\* v18: memory probe retired; adaptive model is Rust-only. \*\//g' "$CTRACE"
sed -i 's/"MEWTWO,9,/"MEWTWO,18,/' "$CTRACE"
