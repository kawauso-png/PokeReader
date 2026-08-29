#!/bin/sh
set -eu

MAIN=3gx/sources/main.c
GEN1=reader_core/src/gen1/mod.rs
TITLE=reader_core/src/title.rs
LIB=reader_core/src/lib.rs
PNP=3gx/sources/pnp.c
PLG=3gx/PokeReader.plgInfo

need() {
  file="$1"
  text="$2"
  msg="$3"
  if ! grep -Fq "$text" "$file"; then
    echo "AUDIT FAIL: $msg" >&2
    exit 1
  fi
}

need "$TITLE" 'BlueJp = 0x0004000000170E00' 'Blue title id missing'
need "$TITLE" '(LoadedTitle::BlueJp, 0)' 'Blue hardware version 0 missing'
need "$TITLE" '(LoadedTitle::BlueJp, 1)' 'real-hardware Blue update version 1 missing'
need "$TITLE" '(LoadedTitle::BlueJp, 1056)' 'Blue remaster 1056 missing'
need "$LIB" 'LoadedTitle::BlueJp => gen1::init_blue()' 'Blue initialize route missing'
need "$LIB" 'LoadedTitle::BlueJp => gen1::run_frame()' 'Blue per-frame route missing'
need "$PLG" '0x00170E00' 'Blue 3GX target missing'

need "$MAIN" '#define BLUE_FIXED_FRAMES 2' 'fixed frame count is not 2'
need "$MAIN" 'blue_fixed_frames_remaining--' 'one-frame gate missing'
need "$MAIN" 'blue_wait_a_release = true' 'post-2F A release gate missing'
need "$MAIN" 'if ((held & KEY_A) == 0)' 'A hold enforcement missing'
need "$MAIN" 'blue_capture_target(blue_fixed_run_id)' 'frozen target capture missing'
need "$MAIN" 'if ((just_pressed & KEY_R) && !(held & KEY_A))' 'Blue R-only resume guard missing'

if grep -Fq 'arm_suicune_probe' "$MAIN"; then
  echo 'AUDIT FAIL: Suicune probe leaked into Blue host path' >&2
  exit 1
fi

fixed_line=$(grep -nF 'if ((just_pressed & KEY_L) && (held & KEY_Y)' "$MAIN" | head -1 | cut -d: -f1)
plain_line=$(grep -nF 'if ((just_pressed & KEY_L) && !(held & KEY_Y))' "$MAIN" | head -1 | cut -d: -f1)
[ "$fixed_line" -lt "$plain_line" ] || { echo 'AUDIT FAIL: fixed Y+L must precede plain L' >&2; exit 1; }

capture_line=$(grep -nF 'blue_capture_target(blue_fixed_run_id)' "$MAIN" | head -1 | cut -d: -f1)
frames_line=$(grep -nF 'blue_fixed_frames_remaining = BLUE_FIXED_FRAMES' "$MAIN" | head -1 | cut -d: -f1)
[ "$capture_line" -lt "$frames_line" ] || { echo 'AUDIT FAIL: target capture must precede first A frame' >&2; exit 1; }

for token in 0x0022_F6C8 0x0022_F6D8 0x0022_F794 0x0022_F5FC 0xFFD3 0xFFD4 0xFFD5 0xD034 0xD036 0xCFCC 0xCFD8 0xCFD9 0xCFDA; do
  need "$GEN1" "$token" "validated Blue address missing: $token"
done

need "$GEN1" 'pub extern "C" fn blue_capture_target(run_id: u32)' 'run-id target capture missing'
need "$GEN1" 'DV_MIN_BATTLE_AGE' 'DV battle-age guard missing'
need "$GEN1" 'DV_STABLE_COUNT' 'DV stable-count guard missing'
need "$GEN1" 'state.stability.observe' 'DV stability state machine unused'

if grep -Fq 'pnp::is_just_pressed' "$GEN1"; then
  echo 'AUDIT FAIL: loose physical-A edge heuristic returned' >&2
  exit 1
fi
if grep -Fq 'last_valid_2f_a' "$GEN1"; then
  echo 'AUDIT FAIL: stale-A heuristic returned' >&2
  exit 1
fi

# Japanese Blue previously produced VC backing addresses 08BAxxxx/08BBxxxx.
# A raw pointer is never exposed to Rust until a fixed slot produces the same
# valid candidate on two separate snapshot reads. Until then host_read_mem
# returns zero, making resolve_ptr_slot stop before dereference.
need "$PNP" '#define BLUE_VC_BACKING_MIN 0x08B00000u' 'tight Blue VC backing lower bound missing'
need "$PNP" '#define BLUE_VC_BACKING_MAX 0x08C00000u' 'tight Blue VC backing upper bound missing'
need "$PNP" '#define BLUE_PTR_STABLE_SAMPLES 2u' 'two-sample pointer stabilization missing'
need "$PNP" 'u32 stable = host_blue_stable_ptr(game_addr);' 'pointer slot reads are not stabilized'
need "$PNP" 'candidate == state->last_candidate' 'consecutive pointer equality check missing'
need "$PNP" 'state->stable_samples >= BLUE_PTR_STABLE_SAMPLES ? candidate : 0' 'unstable pointer is not suppressed'
need "$PNP" 'candidate < BLUE_VC_BACKING_MIN || candidate >= BLUE_VC_BACKING_MAX || !query_resolves(candidate)' 'candidate range/query validation missing'
need "$PNP" 'return query_resolves(addr);' 'mapped reads do not require kernel query resolution'

# Raw fixed-slot diagnostics: display/classify only; stabilization remains the
# only path that can expose a candidate to Rust.
need "$PNP" 'u32 candidate = *(vu32 *)game_addr;' 'safe fixed-slot diagnostic read missing'
need "$PNP" 'blue_print_raw_ptr_diag(game_addr, candidate);' 'raw pointer diagnostic not emitted'
need "$PNP" '"RAW %c %08lX R%d Q%d"' 'raw pointer diagnostic format changed'

# Version-1 host-state discovery is deliberately observational. It scans only
# 0x22F500-0x22F8FF (one already-used emulator-state page), recognizes broad
# 0x08xxxxxx-looking VALUES, prints at most five source/value pairs, and never
# uses those values as addresses or automatically changes W/H/D slot constants.
need "$PNP" '#define BLUE_SCAN_MIN 0x0022F500u' 'bounded scan lower address missing'
need "$PNP" '#define BLUE_SCAN_MAX 0x0022F900u' 'bounded scan upper address missing'
need "$PNP" '#define BLUE_SCAN_VALUE_MIN 0x08000000u' 'scan candidate lower range missing'
need "$PNP" '#define BLUE_SCAN_VALUE_MAX 0x09000000u' 'scan candidate upper range missing'
need "$PNP" '#define BLUE_SCAN_MAX_PRINT 5u' 'scan output bound missing'
need "$PNP" 'for (u32 addr = BLUE_SCAN_MIN; addr < BLUE_SCAN_MAX; addr += sizeof(u32))' 'bounded host-state scan loop missing'
need "$PNP" 'u32 value = *(vu32 *)addr;' 'host-state word observation missing'
need "$PNP" 'hit_addr[shown] = addr;' 'scan source address is not retained'
need "$PNP" 'hit_value[shown] = value;' 'scan candidate value is not retained'
need "$PNP" '"S %08lX > %08lX"' 'scan source/value display missing'
need "$PNP" 'if (game_addr == BLUE_WRAM_PTR_SLOT)' 'scan is not limited to once per Snapshot'
need "$PNP" 'blue_scan_host_state_ptrs();' 'host-state scan is not invoked'

# The scanner must not auto-adopt a discovered slot. The historical slot
# constants stay unchanged until hardware evidence identifies replacements.
need "$PNP" '#define BLUE_WRAM_PTR_SLOT 0x0022F6C8u' 'W slot changed before validation'
need "$PNP" '#define BLUE_HRAM_PTR_SLOT 0x0022F6D8u' 'H slot changed before validation'
need "$PNP" '#define BLUE_DIV_PTR_SLOT  0x0022F794u' 'D slot changed before validation'

if grep -Fq 'MEMPERM_READ' "$PNP"; then
  echo 'AUDIT FAIL: MEMPERM_READ gate breaks Japanese Blue VC backing RAM' >&2
  exit 1
fi
if grep -Fq 'MEMSTATE_FREE' "$PNP"; then
  echo 'AUDIT FAIL: MEMSTATE gate breaks Japanese Blue VC backing RAM' >&2
  exit 1
fi

echo 'Blue Mewtwo audit: PASS'
