#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.3 diagnostic build: identify exactly which rows keep Adaptive at H78/80.
# Do not relax READY.  Expose the first two rows that fail the current
# base/residue20 classifier so we can add the missing real transition class.

if ! grep -q 'pub struct BadRow' "$ADPMOD"; then
    awk '
    /pub fn stats\(\) -> AdaptiveStats/ {
        print "#[derive(Clone, Copy, Default)]"
        print "pub struct BadRow {"
        print "    pub delta: u8,"
        print "    pub step: u8,"
        print "    pub gap: u8,"
        print "    pub residue: u8,"
        print "    pub special: bool,"
        print "}"
        print ""
        print "#[derive(Clone, Copy, Default)]"
        print "pub struct BadRows {"
        print "    pub count: u8,"
        print "    pub first: BadRow,"
        print "    pub second: BadRow,"
        print "}"
        print ""
        print "pub fn bad_rows() -> BadRows {"
        print "    unsafe {"
        print "        if COUNT == 0 { return BadRows::default(); }"
        print "        let s = calculate();"
        print "        let mut out = BadRows::default();"
        print "        for i in 0..COUNT {"
        print "            let r = row_at_oldest(i);"
        print "            let d = r.k.wrapping_sub(s.base);"
        print "            let residue = (r.seq % 20) as u8;"
        print "            let special = residue == s.residue20;"
        print "            let ok = if special {"
        print "                allowed_special(d, r.step, r.gap)"
        print "            } else {"
        print "                allowed_normal(d, r.step, r.gap)"
        print "            };"
        print "            if !ok {"
        print "                let b = BadRow { delta: d, step: r.step, gap: r.gap, residue, special };"
        print "                if out.count == 0 { out.first = b; }"
        print "                else if out.count == 1 { out.second = b; }"
        print "                out.count = out.count.saturating_add(1);"
        print "            }"
        print "        }"
        print "        out"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

if ! grep -q 'BAD1 d{:02X}' "$RUST"; then
    awk '
    /pnp::println!\(\"H\{\}\/\{\} M\{\}\/\{\} S\{\} D\{\}\"/ {
        print
        print "        let bad = adaptive_model::bad_rows();"
        print "        if bad.count != 0 {"
        print "            pnp::println!(color = RED, \"BAD1 d{:02X} s{:02X} g{} r{:02}{}\", bad.first.delta, bad.first.step, bad.first.gap, bad.first.residue, if bad.first.special { \"*\" } else { \"\" });"
        print "            if bad.count >= 2 {"
        print "                pnp::println!(color = RED, \"BAD2 d{:02X} s{:02X} g{} r{:02}{}\", bad.second.delta, bad.second.step, bad.second.gap, bad.second.residue, if bad.second.special { \"*\" } else { \"\" });"
        print "            }"
        print "        }"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.2.2 GBSEQ/BLUE LEGEND RNG v8.2.3 BADROW/' "$RUST"
sed -i 's/MOLTRES GBSEQ AUTO/ADAPT BADROW DIAG/' "$RUST"
sed -i 's/"LEGEND,27,/"LEGEND,28,/' "$CTRACE"
