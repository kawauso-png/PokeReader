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
        print "    fn host_blue_autosearch_enabled() -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi
if ! grep -q 'fn host_blue_autosearch_enabled' "$RUST"; then
    awk '
    { print }
    /fn host_blue_autopause_request\(\);/ {
        print "    fn host_blue_autosearch_enabled() -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

# AUTO HUNT is opt-in. It is OFF at plugin/process start and can only be
# toggled while Blue is already paused at the desired encounter position.
if ! grep -q '^static bool blue_autosearch_enabled' "$MAIN"; then
    sed -i '/static bool blue_wait_a_release = false;/a static bool blue_autosearch_enabled = false;' "$MAIN"
fi

# Requesting pause only flips the already-existing host pause latch. Because
# Rust run_frame executes on the top-screen hook, the bottom-screen hook enters
# handle_freeze(false) before another emulated frame is allowed through.
# AUTO is turned OFF atomically on fire so Exact2F/event frames cannot retrigger.
if ! grep -q '^void host_blue_autopause_request(void)' "$MAIN"; then
    awk '
    /static void reset_blue_fixed_transient\(void\)/ {
        print "u32 host_blue_autosearch_enabled(void)"
        print "{"
        print "    return blue_autosearch_enabled ? 1u : 0u;"
        print "}"
        print ""
        print "void host_blue_autopause_request(void)"
        print "{"
        print "    if (is_blue_jp() && blue_autosearch_enabled && !blue_fixed_pending &&"
        print "        blue_fixed_frames_remaining == 0 && !blue_wait_a_release)"
        print "    {"
        print "        blue_autosearch_enabled = false;"
        print "        is_paused = true;"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$MAIN" > "$MAIN.tmp"
    mv "$MAIN.tmp" "$MAIN"
fi
if ! grep -q '^u32 host_blue_autosearch_enabled(void)' "$MAIN"; then
    awk '
    /void host_blue_autopause_request\(void\)/ {
        print "u32 host_blue_autosearch_enabled(void)"
        print "{"
        print "    return blue_autosearch_enabled ? 1u : 0u;"
        print "}"
        print ""
    }
    { print }
    ' "$MAIN" > "$MAIN.tmp"
    mv "$MAIN.tmp" "$MAIN"
fi

# While paused, Y+X toggles Auto Hunt without allowing a game frame through.
# Keep it before the Y+L Exact2F trigger and reject A/L/R modifiers.
if ! grep -q 'AUTO HUNT enable toggle' "$MAIN"; then
    awk '
    /\/\/ Fixed 2F trigger MUST be checked before the ordinary L single/ {
        print "            // AUTO HUNT enable toggle: paused-only, never reaches the GB."
        print "            if ((just_pressed & KEY_X) && (held & KEY_Y) &&"
        print "                !(held & (KEY_A | KEY_L | KEY_R)))"
        print "            {"
        print "                blue_autosearch_enabled = !blue_autosearch_enabled;"
        print "                continue;"
        print "            }"
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
        print "        let auto_enabled = host_blue_autosearch_enabled() != 0;"
        print "        let auto = autopause::observe(current.seq, adp, fc, auto_enabled);"
        print "        if autopause::take_fire() {"
        print "            host_blue_autopause_request();"
        print "        }"
        infc = 0
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
else
    # Upgrade an earlier v7.7 prep which called the 3-argument observe().
    sed -i 's/let auto = autopause::observe(current.seq, adp, fc);/let auto_enabled = host_blue_autosearch_enabled() != 0;\n        let auto = autopause::observe(current.seq, adp, fc, auto_enabled);/' "$RUST"
fi

if ! grep -q 'AUTO OFF Y+X@PAUSE' "$RUST"; then
    awk '
    /pnp::println!\(\"FC NOW C\{\} S\{\} P\{\}\"/ {
        print
        print "        if !auto.enabled {"
        print "            pnp::println!(\"AUTO OFF Y+X@PAUSE\");"
        print "        } else if auto.fired {"
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
else
    # If an older overlay block was injected by a previous prepare pass, it is
    # already absent in a clean CI checkout. This branch keeps prep idempotent.
    true
fi

sed -i 's/BLUE MEWTWO RNG v7.6.0 FCST/BLUE MEWTWO RNG v7.7.0 AUTO/' "$RUST"
sed -i 's/SHINY FORECAST READ-ONLY/AUTOPAUSE CANDIDATE MODE/' "$RUST"
sed -i 's/"MEWTWO,19,/"MEWTWO,20,/' "$CTRACE"
