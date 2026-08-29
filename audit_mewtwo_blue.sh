#!/bin/sh
set -eu

MAIN=3gx/sources/main.c
GEN1=reader_core/src/gen1/mod.rs
TITLE=reader_core/src/title.rs
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
need "$TITLE" '(LoadedTitle::BlueJp, 1056)' 'Blue remaster 1056 missing'
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

need "$PNP" 'info.state == MEMSTATE_FREE' 'FREE memory not rejected'
need "$PNP" 'info.perm & MEMPERM_READ' 'read permission not checked'

echo 'Blue Mewtwo audit: PASS'
