#!/usr/bin/env python3
from pathlib import Path

H = Path('reader_core/src/crystal/hook.rs').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()
M = Path('3gx/sources/main.c').read_text()


def need(x, m, label):
    if m not in x:
        raise SystemExit('v732 missing ' + label + ': ' + m)


def forbid(x, m, label):
    if m in x:
        raise SystemExit('v732 forbidden ' + label + ': ' + m)

# Proven execution path unchanged.
need(M, '(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)', 'UP+B trigger')
need(M, 'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)', 'B release gate')
need(M, 'suicune_auto_resume_pending && !(held & KEY_DUP)', 'UP safety')
need(T, 'S732 TEST UP+B', 'v732 execution UI')

# v7.3.1 paired reset detector and full observer wipe remain.
need(H, 'VC_DIV_DISCONT_EPOCH', 'paired reset epoch')
need(H, 'VC_DIV_A_ADV == now_advance', 'A/S pair')
need(H, 'pub fn reset_vc_session_observers()', 'observer wipe')
for m in [
    'RNG_ADVANCE = 0',
    'ADD_DIV_TRACKER = DivTracker::new()',
    'SUB_DIV_TRACKER = DivTracker::new()',
    'PRE_VBLANK_RING = PreVBlankRing::EMPTY',
    'CALL_COUNT = 0',
    'DEEP_COUNT = 0',
    'ENDPOINT_FAST_TAIL = false',
]:
    need(H, m, 'observer wipe ' + m)

# Hardware bug fix: baseline must be captured in healthy SCAN, never at reset.
need(T, 'self.soft_reset_expected_tid = reader.trainer_id();', 'healthy SCAN TID baseline')
need(T, 'self.soft_reset_play_marker = Self::play_marker(reader);', 'healthy SCAN play baseline')
need(T, 'let expected_tid = self.soft_reset_expected_tid;', 'preserve cached TID at reset')
need(T, 'let old_play = self.soft_reset_play_marker;', 'preserve cached play marker')
forbid(T, 'let expected_tid = reader.trainer_id();', 'late reset-time TID capture')

# Loaded-save gate still verifies same save identity and sane party.
need(T, 'reader.trainer_id() == self.soft_reset_expected_tid', 'same save TID gate')
need(T, 'gb_mem::read_u8(0xdc9d)', 'party count gate')
need(T, 'gb_mem::read_u8(0xdc9e)', 'first species gate')

# Rearm freshness is derived solely from observers that were explicitly wiped.
need(T, 'let rr = latest_pre_vblank_ring();', 'fresh ring')
need(T, 'rn == PRE_VBLANK_RING_LEN', 'full ring')
need(T, 'rng_advance().wrapping_sub(last_adv) <= 1', 'current ring')
need(T, 'add_div_tracker().index().is_some()', 'fresh A index')
need(T, 'sub_div_tracker().index().is_some()', 'fresh S index')
need(T, 'if self.soft_reset_loaded_streak < 8 { return true; }', 'stable rearm streak')
need(T, 'self.search_practical_targets(reader);', 'automatic fresh SCAN')
forbid(T, 'self.soft_reset_saw_unloaded || play_moved', 'play-time deadlock gate')

# Runtime reset and GlobalBeam safeguards remain intact.
need(T, 'let mut fresh = Self::default();', 'Trace default reset')
need(T, 'fresh.practical_live_scan = false;', 'no title-screen scanner')
need(T, 'fn practical_wait_monitor', 'live monitor')
need(T, 'fn rebind_shiny_post_v730', 'GlobalBeam rebind')
need(T, 'practical_expected716_state', 'rel716 guard')
need(T, 'practical_expected717_state', 'rel717 guard')
need(T, 'S732 RESET WAIT', 'reset wait UI')
need(T, 'S732 SCAN', 'fresh scan UI')
need(T, 'GLOBALBEAM,V732', 'v732 telemetry')
need(T, 'SOFTRESET,V732', 'reset telemetry')
forbid(T, 'S731 ', 'stale v731 UI')

print('v7.3.2 AUDIT PASS: healthy-SCAN save baseline survives soft reset; no reset-time TID capture; rearm uses wiped fresh ring/A/S indices without play-time deadlock; UP+B and GlobalBeam hard guards preserved')
