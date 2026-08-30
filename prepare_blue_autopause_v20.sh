#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
MAIN=3gx/sources/main.c
CTRACE=3gx/sources/blue_dvtrace.c

if ! grep -q '^mod autopause;$' "$RUST"; then
    sed -i '1imod autopause;' "$RUST"
fi

if ! grep -q 'fn host_blue_autopause_request' "$RUST"; then
    awk '
    { print }
    /fn host_blue_gbrelease_valid\(\) -> u32;/ {
        print "    fn host_blue_autopause_request();"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

# Requesting pause only flips the already-existing host pause latch. Because
# Rust run_frame executes on the top-screen hook, the bottom-screen hook enters
# handle_freeze(false) before another emulated frame is allowed through.
if ! grep -q '^void host_blue_autopause_request(void)' "$MAIN"; then
    awk '
    /static void reset_blue_fixed_transient\(void\)/ {
        print "void host_blue_autopause_request(void)"
        print "{"
        print "    if (is_blue_jp() && !blue_fixed_pending &&"
        print "        blue_fixed_frames_remaining == 0 && !blue_wait_a_release)"
        print "        is_paused = true;"
        print "}"
        print ""
    }
    { print }
    ' "$MAIN" > "$MAIN.tmp"
    mv "$MAIN.tmp" "$MAIN"
fi

if ! grep -q 'let auto = autopause::observe' "$RUST"; then
    awk '
    BEGIN { infc = 0 }
    /let fc = shiny_forecast::scan\(/ { infc = 1 }
    { print }
    infc && /^[[:space:]]*\);/ {
        print "        let auto = autopause::observe(current.seq, adp, fc);"
        print "        if autopause::take_fire() {"
        print "            host_blue_autopause_request();"
        print "        }"
        infc = 0
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'AUTO PAUSED C{} S{}' "$RUST"; then
    awk '
    /pnp::println!\(\"FC NOW C\{\} S\{\} P\{\}\"/ {
        print
        print "        if auto.fired {"
        print "            pnp::println!(color = GREEN, \"AUTO PAUSED C{} S{}\", auto.candidates, auto.shiny);"
        print "        } else if auto.latched {"
        print "            pnp::println!(color = YELLOW, \"AUTO +{} C{} S{}\", auto.remain, auto.candidates, auto.shiny);"
        print "        } else {"
        print "            pnp::println!(\"AUTO SEARCH\");"
        print "        }"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE MEWTWO RNG v7.6.0 FCST/BLUE MEWTWO RNG v7.7.0 AUTO/' "$RUST"
sed -i 's/SHINY FORECAST READ-ONLY/AUTOPAUSE CANDIDATE MODE/' "$RUST"
sed -i 's/"MEWTWO,19,/"MEWTWO,20,/' "$CTRACE"
