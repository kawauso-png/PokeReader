#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.2.5 diagnostic: expose the last-16 DIV step pattern and the minimum
# mismatch count against the exact +20/64 subphase model. This tells us whether
# S0/D0 is caused by one/two sampled-phase jitters or by a wrong cadence model.

if ! grep -q 'pub struct DivDiag' "$ADPMOD"; then
    awk '
    /pub fn stats\(\) -> AdaptiveStats/ {
        print "#[derive(Clone, Copy, Default)]"
        print "pub struct DivDiag {"
        print "    pub pattern: u16,"
        print "    pub best_err: u8,"
        print "    pub best_count: u8,"
        print "}"
        print ""
        print "pub fn div_diag() -> DivDiag {"
        print "    unsafe {"
        print "        if COUNT == 0 { return DivDiag::default(); }"
        print "        let use_n = core::cmp::min(COUNT, DIV_WIN);"
        print "        let first_i = COUNT - use_n;"
        print "        let mut pattern = 0u16;"
        print "        for j in 0..use_n {"
        print "            let r = row_at_oldest(first_i + j);"
        print "            if r.step == 0x13 { pattern |= 1u16 << j; }"
        print "        }"
        print "        let mut best_err = 0xFFu8;"
        print "        let mut best_count = 0u8;"
        print "        for start_sub in 0u8..64u8 {"
        print "            let mut sub = start_sub;"
        print "            let mut err = 0u8;"
        print "            for i in first_i..COUNT {"
        print "                let r = row_at_oldest(i);"
        print "                let expect = 0x12u8 + u8::from((sub as u16 + 20u16) >= 64u16);"
        print "                if r.step != expect { err = err.saturating_add(1); }"
        print "                sub = sub.wrapping_add(20) & 0x3F;"
        print "            }"
        print "            if err < best_err { best_err = err; best_count = 1; }"
        print "            else if err == best_err { best_count = best_count.saturating_add(1); }"
        print "        }"
        print "        DivDiag { pattern, best_err, best_count }"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

if ! grep -q 'DIV16 {:04X} E{} C{}' "$RUST"; then
    awk '
    /pnp::println!\(\"H\{\}\/\{\} M\{\}\/\{\} S\{\} D\{\}\"/ {
        print
        print "        let dd = adaptive_model::div_diag();"
        print "        pnp::println!(color = YELLOW, \"DIV16 {:04X} E{} C{}\", dd.pattern, dd.best_err, dd.best_count);"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.2.4 SPFIX/BLUE LEGEND RNG v8.2.5 DIVDIAG/' "$RUST"
sed -i 's/ADAPT SPECIAL FIX/DIV PHASE DIAG/' "$RUST"
sed -i 's/"LEGEND,29,/"LEGEND,30,/' "$CTRACE"
