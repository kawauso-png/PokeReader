#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
AUTOMOD=reader_core/src/gen1/autopause.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.4.6 Articuno weighted AutoPause.
#
# Hardware traces 0017..0023 all had their generated raw DV inside the broad
# Articuno forecast envelope, so keep that envelope unchanged for coverage.
# The issue was stop quality: AutoPause fired whenever any shiny raw existed,
# even when that shiny raw lived only on a fringe timing branch.
#
# Articuno hardware microphase observations are tightly concentrated at the
# +91/+92 M-cycle common timing family (trace0016=91; 0017..0022=92; 0023=91).
# Score NOW using only this high-confidence timing core while preserving the
# old +90..+94 envelope for diagnostic containment.
#
# Replayed core shiny-path support at the seven failed stops:
#   0017 16/96  = 16.7%
#   0018 16/96  = 16.7%
#   0019  0/96  =  0.0%
#   0020 11/184 =  6.0%
#   0021  6/96  =  6.3%
#   0022 80/192 = 41.7%
#   0023  1/152 =  0.7%
# Therefore target 2 only fires when weighted core shiny support >=25%.
# This is a branch-support score, not a claim of literal encounter probability.

if ! grep -q 'ARTICUNO_WEIGHT25_V45' "$FCMOD"; then
    awk '
    /unsafe fn collect_articuno_event\(add: u8, div: u8, phase: u8,/ {
        print "// ARTICUNO_WEIGHT25_V45: high-confidence +91/+92 M-cycle core score."
        print "fn articuno_core_weight_one_phase(add: u8, div: u8, phase: u8) -> (u16, u16) {"
        print "    let mut total = 0u16;"
        print "    let mut shiny_weight = 0u16;"
        print "    for jump in [0u8, 60u8, 56u8] {"
        print "        let p0 = phase.wrapping_add(jump) & 0x3F;"
        print "        let pre = run_articuno_event_path(add, div, p0);"
        print "        // Keep scoring narrow (+91/+92), while collect_battle keeps the"
        print "        // wider +90..+94 containment envelope for diagnostics."
        print "        let qv_lo = ((pre.2 as u16 + 2144u16) / 64) as u8; // 2053 + 91"
        print "        let qv_hi = ((pre.2 as u16 + 2163u16) / 64) as u8; // 2071 + 92"
        print "        let mut qv = qv_lo;"
        print "        loop {"
        print "            let mut tb = 5752u16; // 5661 + 91"
        print "            while tb <= 5759u16 { // 5667 + 92"
        print "                let qb1 = ((pre.2 as u16 + tb) / 64) as u8;"
        print "                let qb2 = ((pre.2 as u16 + tb + 120) / 64) as u8;"
        print "                let rv = pre.1.wrapping_add(qv);"
        print "                let rb1 = pre.1.wrapping_add(qb1);"
        print "                let rb2 = pre.1.wrapping_add(qb2);"
        print "                let low = pre.0.wrapping_add(rv).wrapping_add(rb1).wrapping_add(1);"
        print "                let high = low.wrapping_add(rb2).wrapping_add(1);"
        print "                let raw = ((high as u16) << 8) | low as u16;"
        print "                total = total.saturating_add(1);"
        print "                if shiny(raw) { shiny_weight = shiny_weight.saturating_add(1); }"
        print "                tb += 1;"
        print "            }"
        print "            if qv == qv_hi { break; }"
        print "            qv = qv.wrapping_add(1);"
        print "        }"
        print "    }"
        print "    (total, shiny_weight)"
        print "}"
        print ""
        print "unsafe fn articuno_core_weight_now(count_states: usize) -> (u16, u16) {"
        print "    let mut total = 0u16;"
        print "    let mut shiny_weight = 0u16;"
        print "    for i in 0..count_states {"
        print "        let s = CUR[i];"
        print "        let w = articuno_core_weight_one_phase(s.add, s.div, s.phase);"
        print "        total = total.saturating_add(w.0);"
        print "        shiny_weight = shiny_weight.saturating_add(w.1);"
        print "    }"
        print "    (total, shiny_weight)"
        print "}"
        print ""
    }
    { print }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"

    # Add the score to ForecastStats.  The broad raw candidate counts stay
    # untouched; these fields are only an AutoPause quality signal.
    sed -i '/pub now_shiny: u8,/a\    pub now_weight_total: u16,\
    pub now_shiny_weight: u16,\
    pub now_shiny_pct: u8,' "$FCMOD"

    # Complete explicit ForecastStats initializers in shiny_forecast.rs.
    sed -i 's/now_candidates: 0, now_shiny: 0,/now_candidates: 0, now_shiny: 0, now_weight_total: 0, now_shiny_weight: 0, now_shiny_pct: 0,/' "$FCMOD"

    # Compute weighted NOW immediately after the broad current evaluation.
    awk '
    { print }
    /out\.now_shiny = now\.1;/ {
        print "    if LEGEND_TARGET_ID == 2 {"
        print "        let w = articuno_core_weight_now(n);"
        print "        out.now_weight_total = w.0;"
        print "        out.now_shiny_weight = w.1;"
        print "        out.now_shiny_pct = if w.0 == 0 { 0 } else {"
        print "            (((w.1 as u32) * 100u32) / (w.0 as u32)) as u8"
        print "        };"
        print "    }"
    }
    ' "$FCMOD" > "$FCMOD.tmp"
    mv "$FCMOD.tmp" "$FCMOD"

    cat >> "$FCMOD" <<'EOF'

#[cfg(test)]
mod articuno_weight25_v45_tests {
    use super::*;

    fn sum(add: u8, div: u8, phases: &[u8]) -> (u16, u16) {
        let mut total = 0u16;
        let mut shiny_weight = 0u16;
        for &p in phases {
            let w = articuno_core_weight_one_phase(add, div, p);
            total += w.0;
            shiny_weight += w.1;
        }
        (total, shiny_weight)
    }

    #[test]
    fn replay_0017_is_below_weight25() {
        let w = sum(0x0A, 0x9A, &[20, 21, 22, 23]);
        assert_eq!(w, (96, 16));
        assert!((w.1 as u32) * 100 < (w.0 as u32) * 25);
    }

    #[test]
    fn replay_0022_is_high_confidence_weight25() {
        let w = sum(0x7D, 0x69, &[60, 61, 62, 63]);
        assert_eq!(w, (192, 80));
        assert!((w.1 as u32) * 100 >= (w.0 as u32) * 25);
    }

    #[test]
    fn replay_0023_fringe_shiny_is_rejected() {
        let w = sum(0x30, 0xAA, &[52, 53, 54, 55]);
        assert_eq!(w, (152, 1));
        assert!((w.1 as u32) * 100 < (w.0 as u32) * 25);
    }
}
EOF
fi

# ForecastStats is also constructed directly in autopause unit tests.
if ! grep -q 'now_weight_total' "$AUTOMOD"; then
    sed -i 's/now_candidates, now_shiny,/now_candidates, now_shiny, now_weight_total: 0, now_shiny_weight: 0, now_shiny_pct: 0,/' "$AUTOMOD"
fi

# Target 2 now requires >=25% high-confidence weighted shiny-path support.
if ! grep -q 'ARTICUNO_WEIGHT_GATE_V45' "$AUTOMOD"; then
    awk '
    /pub fn observe\(/ {
        print "fn weighted_gate(target: u8, fc: &ForecastStats) -> bool { // ARTICUNO_WEIGHT_GATE_V45"
        print "    if target != 2 { return true; }"
        print "    fc.now_weight_total != 0 && fc.now_shiny_weight != 0"
        print "        && (fc.now_shiny_weight as u32) * 100u32"
        print "            >= (fc.now_weight_total as u32) * 25u32"
        print "}"
        print ""
    }
    { print }
    ' "$AUTOMOD" > "$AUTOMOD.tmp"
    mv "$AUTOMOD.tmp" "$AUTOMOD"

    sed -i '/&& fc.now_shiny != 0/a\            && weighted_gate(LEGEND_TARGET_ID, \&fc)' "$AUTOMOD"

    cat >> "$AUTOMOD" <<'EOF'

#[cfg(test)]
mod articuno_weight_gate_v45_tests {
    use super::*;

    fn f(total: u16, shiny_weight: u16) -> ForecastStats {
        ForecastStats {
            valid: true,
            now_candidates: 7,
            now_shiny: 1,
            now_weight_total: total,
            now_shiny_weight: shiny_weight,
            now_shiny_pct: if total == 0 { 0 } else { ((shiny_weight as u32 * 100) / total as u32) as u8 },
            ..ForecastStats::default()
        }
    }

    #[test]
    fn articuno_rejects_fringe_weight() {
        assert!(!weighted_gate(2, &f(152, 1)));
        assert!(!weighted_gate(2, &f(96, 16)));
    }

    #[test]
    fn articuno_accepts_high_weight() {
        assert!(weighted_gate(2, &f(192, 80)));
    }

    #[test]
    fn other_targets_keep_existing_gate() {
        assert!(weighted_gate(0, &f(0, 0)));
        assert!(weighted_gate(1, &f(0, 0)));
        assert!(weighted_gate(3, &f(0, 0)));
    }
}
EOF
fi

# Show the score explicitly; it is a path-support score, not a literal percent
# chance.  Keep the broad FC C/S display beside it for diagnostics.
if ! grep -q 'ARTW {}/{} {}%' "$RUST"; then
    sed -i '/pnp::println!("FC NOW C{} S{} P{}"/a\        if legend_target == 2 { pnp::println!(color = if fc.now_shiny_pct >= 25 { GREEN } else { WHITE }, "ARTW {}/{} {}%", fc.now_shiny_weight, fc.now_weight_total, fc.now_shiny_pct); }' "$RUST"
fi
sed -i 's/ARTICUNO AUTO 11F\/9F/ARTICUNO W25 11F\/9F/' "$RUST"
sed -i 's/BLUE LEGEND RNG v8.4.5 ART BASE40/BLUE LEGEND RNG v8.4.6 ART W25/' "$RUST"
sed -i 's/"LEGEND,44,/"LEGEND,45,/' "$CTRACE"

# Build-time guards.
grep -q 'ARTICUNO_WEIGHT25_V45' "$FCMOD"
grep -q 'pub now_weight_total: u16' "$FCMOD"
grep -q 'articuno_core_weight_now' "$FCMOD"
grep -q 'replay_0022_is_high_confidence_weight25' "$FCMOD"
grep -q 'ARTICUNO_WEIGHT_GATE_V45' "$AUTOMOD"
grep -q 'weighted_gate(LEGEND_TARGET_ID, &fc)' "$AUTOMOD"
grep -q 'ARTW {}/{} {}%' "$RUST"
grep -q 'BLUE LEGEND RNG v8.4.6 ART W25' "$RUST"
grep -q '"LEGEND,45,' "$CTRACE"
