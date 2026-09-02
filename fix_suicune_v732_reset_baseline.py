#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/trace.rs')
s = P.read_text()


def function_span(text: str, signature: str):
    start = text.find(signature)
    if start < 0:
        raise SystemExit('v732 function not found: ' + signature)
    brace = text.find('{', start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return start, i + 1
    raise SystemExit('v732 unclosed: ' + signature)

# ---------------------------------------------------------------------------
# Root cause of the hardware P/X/EV/SK=0 report:
# v7.3.1 captured trainer_id/play-time at the moment the DIV discontinuity was
# noticed. By then Crystal can already be in boot/title WRAM, so the expected
# TID can be zero/transient and RESET WAIT can never accept the loaded save.
# Capture the known-good save identity when SCAN starts instead.
# ---------------------------------------------------------------------------
ss, se = function_span(s, '    pub fn search_practical_targets')
search = s[ss:se]
if '_reader: &Gen2Reader' in search:
    search = search.replace('_reader: &Gen2Reader', 'reader: &Gen2Reader', 1)
elif 'reader: &Gen2Reader' not in search:
    raise SystemExit('v732 search reader parameter not found')

anchor = '''        self.soft_reset_rearm_pending = false;\n        self.soft_reset_loaded_streak = 0;\n'''
if search.count(anchor) != 1:
    raise SystemExit(f'v732 search baseline anchor count {search.count(anchor)}')
search = search.replace(
    anchor,
    anchor + '''        // v7.3.2: snapshot the identity of the *loaded save* while SCAN is\n        // definitely healthy. Never derive this baseline during boot/reset WRAM.\n        self.soft_reset_expected_tid = reader.trainer_id();\n        self.soft_reset_play_marker = Self::play_marker(reader);\n        self.soft_reset_saw_unloaded = false;\n''',
    1,
)
s = s[:ss] + search + s[se:]

# Preserve that pre-reset baseline through the Default-based session wipe.
old = '''                let expected_tid = reader.trainer_id();\n                let old_play = Self::play_marker(reader);\n'''
new = '''                // v7.3.2: preserve the known-good SCAN baseline. Reading\n                // TID here is too late: VC reset may already have changed WRAM.\n                let expected_tid = self.soft_reset_expected_tid;\n                let old_play = self.soft_reset_play_marker;\n'''
if s.count(old) != 1:
    raise SystemExit(f'v732 reset baseline anchor count {s.count(old)}')
s = s.replace(old, new, 1)

# Once reset_vc_session_observers() has wiped PRE ring and A/S trackers, a full
# current ring plus re-locked trackers is itself proof of post-reset freshness.
# Requiring play time to move can deadlock at the loaded save for a second or
# indefinitely if the user reaches the wait screen before the game clock ticks.
start_marker = '''        // If WRAM was visibly cleared, a valid signature is enough. If the VC\n'''
end_marker = '''        if self.soft_reset_loaded_streak < 8 { return true; }\n'''
start = s.find(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('v732 old boot-transition gate not found')
end += len(end_marker)
replacement = '''        // v7.3.2: observer wipe makes freshness self-proving. The ring and\n        // both tracker indices below were reset to EMPTY/new at the reset\n        // boundary, so they cannot be inherited from the previous attempt.\n        let rr = latest_pre_vblank_ring();\n        let rn = (rr.count as usize).min(PRE_VBLANK_RING_LEN);\n        let ring_current = if rn == PRE_VBLANK_RING_LEN {\n            let (last_adv, _) = pre_ring_sample(&rr, rn - 1);\n            rng_advance().wrapping_sub(last_adv) <= 1\n        } else {\n            false\n        };\n        let pre_fresh = ring_current\n            && add_div_tracker().index().is_some()\n            && sub_div_tracker().index().is_some();\n\n        if pre_fresh {\n            self.soft_reset_loaded_streak = self.soft_reset_loaded_streak.saturating_add(1);\n        } else {\n            self.soft_reset_loaded_streak = 0;\n        }\n\n        if self.soft_reset_loaded_streak < 8 { return true; }\n'''
s = s[:start] + replacement + s[end:]

# Make the hardware build unmistakable.
s = s.replace('S731 ', 'S732 ')
s = s.replace('GLOBALBEAM,V731', 'GLOBALBEAM,V732')
s = s.replace('SOFTRESET,V731', 'SOFTRESET,V732')

for marker in [
    'S732 SCAN',
    'S732 RESET WAIT',
    'S732 TEST UP+B',
    'GLOBALBEAM,V732',
    'SOFTRESET,V732',
    'self.soft_reset_expected_tid = reader.trainer_id();',
    'let expected_tid = self.soft_reset_expected_tid;',
    'let rr = latest_pre_vblank_ring();',
    'add_div_tracker().index().is_some()',
    'sub_div_tracker().index().is_some()',
]:
    if marker not in s:
        raise SystemExit('v732 missing postpatch marker: ' + marker)

if 'self.soft_reset_saw_unloaded || play_moved' in s:
    raise SystemExit('v732 stale play-time boot gate remains')
if 'S731 ' in s:
    raise SystemExit('v732 stale S731 UI remains')

P.write_text(s)
print('Applied Suicune v7.3.2 reset-session fix: healthy-SCAN TID baseline, preserved across wipe, fresh-ring/A/S rearm without play-time deadlock')
