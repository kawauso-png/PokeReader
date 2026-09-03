#!/usr/bin/env python3
from pathlib import Path
m=Path('3gx/sources/main.c').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()

def need(x,msg):
    if not x: raise SystemExit('v741 audit FAIL: '+msg)

# START must be absolute and invariant across B76/B39 target hotkeys.
need('const u32 wanted_start_cycle = 0U;' in m,'absolute START M0 selector missing')
need('cycle = now / SUICUNE_PHASE_PERIOD_TICKS + 1ULL;' in m,'absolute START cycle calculation missing')
need('while (((u32)cycle & 15U) != wanted_start_cycle) cycle++;' in m,'absolute START mod16 lock missing')
need('u64 target = cycle * SUICUNE_PHASE_PERIOD_TICKS;' in m,'absolute START boundary missing')
need('suicune_start_phase_anchor_tick = target;' in m,'absolute START anchor diagnostic missing')
need('suicune_start_phase_slot = 0;' in m,'START M0 fixed state missing')
need('suicune_start_phase_slot ^= 8' not in m,'Y+DOWN can still mutate START phase')
need('suicune_start_phase_slot = (suicune_start_phase_slot + 1)' not in m,'relative START selector remains')
need('suicune_start_phase_anchor_tick + offset' not in m,'relative START anchor path remains')

# Sweep mechanics must remain intact.
need('suicune_phase_slot = 8;' in m,'B76 selector missing')
need('suicune_phase_slot = 9;' in m,'B39 selector missing')
need('suicune_phase_slot = (suicune_phase_slot + 1U) & 7U;' in m,'SLOT0..7 X cycle missing')
need('suicune_wait_up_after_b = true;' in m,'B then UP arm path missing')
need('u32 wanted = suicune_phase_slot & 7U;' in m,'absolute resume slot selector missing')
need('while (((u32)cycle & 7U) != wanted) cycle++;' in m,'absolute resume slot wait missing')

# Telemetry must use actual POST classification and expose START absolute diagnostics.
need('S741 B{} TURBO' in t and 'S741 B{} SWEEP FOUND' in t,'v741 UI missing')
need('ABS START M0' in t,'absolute START UI missing')
need('SWEEP,V741' in t,'v741 sweep CSV missing')
need('classify_post_entries(self.entries,self.len,self.probe_target.advance)' in t,'actual POST classification lost')
need('start_cycle_mod16' in t and 'start_remainder' in t and 'start_error_ticks' in t,'absolute START CSV diagnostics missing')
print('v7.4.1 audit PASS: absolute START cycle mod16=0, no target-hotkey collision, SLOT0..7 absolute resume sweep retained')
