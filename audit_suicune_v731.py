#!/usr/bin/env python3
from pathlib import Path

m = Path('3gx/sources/main.c').read_text()

def need(cond, msg):
    if not cond:
        raise SystemExit('v731 audit FAIL: ' + msg)

need('static u32 suicune_phase_slot = 1;' in m, 'absolute resume slot default is not 1')
need('suicune_phase_slot = 0;' not in m, 'legacy poll still forces resume slot to 0')
need('suicune_start_phase_slot = 0;' in m, 'start phase zero calibration missing')
need('suicune_phase_slot = (suicune_phase_slot == 1) ? 6 : 1;' in m, 'slot1/slot6 toggle missing')
need('u32 wanted = suicune_phase_slot & 7U;' in m, 'absolute resume wait no longer uses selected slot')
need('while (((u32)cycle & 7U) != wanted) cycle++;' in m, 'absolute slot boundary loop missing')
print('v7.3.1 audit PASS: default SLOT1 survives Y+DOWN/Y-held pause polls; SLOT1<->SLOT6 control retained')
