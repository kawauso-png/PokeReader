#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
MAIN=3gx/sources/main.c
CTRACE=3gx/sources/blue_dvtrace.c

# ---------------------------------------------------------------------------
# Shared fixed-legend target table (Blue JP internal species ids).
# 0 Mewtwo 83/L70, 1 Zapdos 4B/L50, 2 Articuno 4A/L50, 3 Moltres 49/L50.
# ---------------------------------------------------------------------------
if ! grep -q 'BLUE_LEGEND_TARGET_COUNT' "$CTRACE"; then
    awk '
    /#define ARM_SOURCE_PHYSICAL_A 3u/ {
        print
        print ""
        print "#define BLUE_LEGEND_TARGET_COUNT 4u"
        print "typedef struct { u8 species; u8 level; const char *name; } BlueLegendTarget;"
        print "static const BlueLegendTarget blue_legend_targets[BLUE_LEGEND_TARGET_COUNT] = {"
        print "    {0x83u, 0x46u, \"MEWTWO\"},"
        print "    {0x4Bu, 0x32u, \"ZAPDOS\"},"
        print "    {0x4Au, 0x32u, \"ARTICUNO\"},"
        print "    {0x49u, 0x32u, \"MOLTRES\"},"
        print "};"
        print "static u32 blue_legend_target = 0u;"
        print ""
        print "u32 host_blue_legend_target_id(void) { return blue_legend_target; }"
        print "u32 host_blue_legend_target_species(void) { return blue_legend_targets[blue_legend_target].species; }"
        print "u32 host_blue_legend_target_level(void) { return blue_legend_targets[blue_legend_target].level; }"
        print "void host_blue_legend_target_step(s32 delta)"
        print "{"
        print "    s32 id = (s32)blue_legend_target + delta;"
        print "    while (id < 0) id += (s32)BLUE_LEGEND_TARGET_COUNT;"
        print "    while (id >= (s32)BLUE_LEGEND_TARGET_COUNT) id -= (s32)BLUE_LEGEND_TARGET_COUNT;"
        print "    blue_legend_target = (u32)id;"
        print "}"
        print "static const char *blue_legend_target_name(void) { return blue_legend_targets[blue_legend_target].name; }"
        next
    }
    { print }
    ' "$CTRACE" > "$CTRACE.tmp"
    mv "$CTRACE.tmp" "$CTRACE"
fi

# Replace every Mewtwo-only encounter/DV-write discriminator with the selected
# fixed legend. The raw-DV address and RNG generator remain common to all four.
sed -i 's/opponent == 0x83/opponent == (u8)host_blue_legend_target_species()/g' "$CTRACE"
sed -i 's/species == 0x83/species == (u8)host_blue_legend_target_species()/g' "$CTRACE"
sed -i 's/level == 0x46/level == (u8)host_blue_legend_target_level()/g' "$CTRACE"

# Record the selected target explicitly in every calibration trace.
if ! grep -q '^static void write_legend_target_row' "$CTRACE"; then
    awk '
    /static void write_meta_row\(Handle file, u64 \*off\)/ {
        print "static void write_legend_target_row(Handle file, u64 *off)"
        print "{"
        print "    char line[160];"
        print "    int n = snprintf(line, sizeof(line),"
        print "        \"legend_target,id,name,species,level\\nTARGET,%lu,%s,%02X,%u\\n\","
        print "        (unsigned long)blue_legend_target, blue_legend_target_name(),"
        print "        (unsigned int)host_blue_legend_target_species(),"
        print "        (unsigned int)host_blue_legend_target_level());"
        print "    if (n > 0) write_bytes(file, off, line, (u32)n);"
        print "}"
        print ""
    }
    { print }
    ' "$CTRACE" > "$CTRACE.tmp"
    mv "$CTRACE.tmp" "$CTRACE"
fi
if ! grep -q 'write_legend_target_row(file, &off);' "$CTRACE"; then
    sed -i '/write_meta_row(file, &off);/a\    write_legend_target_row(file, \&off);' "$CTRACE"
fi

# Generalize file name and metadata label for the four-target tool.
sed -i 's/mewtwo_trace_/legend_trace_/g' "$CTRACE"
sed -i 's/"MEWTWO,22,/"LEGEND,23,/' "$CTRACE"

# ---------------------------------------------------------------------------
# Paused-only target selector. Left/right never reaches the Game Boy because
# selection is handled inside the existing freeze loop. Any target change
# atomically disables Auto Hunt.
# ---------------------------------------------------------------------------
if ! grep -q 'LEGEND target selector' "$MAIN"; then
    awk '
    /\/\/ Fixed 2F trigger MUST be checked before the ordinary L single/ {
        print "            // LEGEND target selector: paused-only, no GB frame passes."
        print "            if ((just_pressed & KEY_DLEFT) && !(held & (KEY_A | KEY_Y | KEY_L | KEY_R)))"
        print "            {"
        print "                host_blue_legend_target_step(-1);"
        print "                blue_autosearch_enabled = false;"
        print "                continue;"
        print "            }"
        print "            if ((just_pressed & KEY_DRIGHT) && !(held & (KEY_A | KEY_Y | KEY_L | KEY_R)))"
        print "            {"
        print "                host_blue_legend_target_step(1);"
        print "                blue_autosearch_enabled = false;"
        print "                continue;"
        print "            }"
        print ""
    }
    { print }
    ' "$MAIN" > "$MAIN.tmp"
    mv "$MAIN.tmp" "$MAIN"
fi

# Only the already hardware-validated Mewtwo event model may AutoPause in v8.0.
# The three birds are calibration-only until their release->DV/event paths are
# measured. Y+X on a bird therefore leaves AUTO OFF.
if ! grep -q 'host_blue_legend_target_id() == 0u' "$MAIN"; then
    sed -i 's/blue_autosearch_enabled = !blue_autosearch_enabled;/if (host_blue_legend_target_id() == 0u)\n                    blue_autosearch_enabled = !blue_autosearch_enabled;\n                else\n                    blue_autosearch_enabled = false;/' "$MAIN"
fi

# ---------------------------------------------------------------------------
# Rust overlay target label + calibration guard.
# ---------------------------------------------------------------------------
if ! grep -q 'fn host_blue_legend_target_id' "$RUST"; then
    awk '
    { print }
    /fn host_blue_autosearch_enabled\(\) -> u32;/ {
        print "    fn host_blue_legend_target_id() -> u32;"
    }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'let legend_target = unsafe' "$RUST"; then
    awk '
    /let current = sample\(\);/ {
        print
        print "    let legend_target = unsafe { host_blue_legend_target_id() };"
        print "    let legend_name = match legend_target {"
        print "        0 => \"MEWTWO\","
        print "        1 => \"ZAPDOS\","
        print "        2 => \"ARTICUNO\","
        print "        3 => \"MOLTRES\","
        print "        _ => \"UNKNOWN\","
        print "    };"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

if ! grep -q 'TARGET {}  </>@PAUSE' "$RUST"; then
    awk '
    /if let Some\(result\) = state.result \{/ {
        print "        pnp::println!(color = BLUE, \"TARGET {}  </>@PAUSE\", legend_name);"
        print "        if legend_target != 0 {"
        print "            pnp::println!(color = YELLOW, \"CALIBRATE: EXACT2F ONLY\");"
        print "        }"
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

# Replace the generic AUTO-OFF line with an explicit calibration lock on birds.
if ! grep -q 'CAL AUTO LOCKED' "$RUST"; then
    sed -i 's/        if !auto.enabled {/        if legend_target != 0 {\n            pnp::println!(color = YELLOW, \"CAL AUTO LOCKED\");\n        } else if !auto.enabled {/' "$RUST"
fi

sed -i 's/BLUE MEWTWO RNG v7.7.2 +4/BLUE LEGEND RNG v8.0 CAL/' "$RUST"
sed -i 's/AUTOPAUSE +4 ENVELOPE/4-LEGEND CALIBRATION/' "$RUST"
