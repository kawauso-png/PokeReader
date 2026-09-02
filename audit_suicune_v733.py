#!/usr/bin/env python3
from pathlib import Path
m=Path('3gx/sources/main.c').read_text()
t=Path('reader_core/src/crystal/trace.rs').read_text()

def need(c,msg):
    if not c: raise SystemExit('v733 audit FAIL: '+msg)

need('static bool suicune_wait_up_after_b = false;' in m,'stage2 state missing')
need('if ((held & KEY_B) && !(held & KEY_Y)' in m,'B-only arm missing')
need('&& suicune_root_lock_ready' in m,'B-only arm not gated by locked root')
need('suicune_wait_up_after_b = true;' in m,'B arm does not enter UP wait')
need('if (suicune_wait_up_after_b)' in m,'UP wait state missing')
need('if (held & KEY_DUP)' in m,'UP-only second stage missing')
need('fixed_run_pending = true;' in m and 'suicune_auto_resume_pending = true;' in m,'Exact2F handoff missing')
need('B ARM -> UP' in t,'new UI instruction missing')
need('S733 A/r10 LOCKED' in t,'v733 locked UI missing')
print('v7.3.3 audit PASS: no simultaneous chord required; B-only ARM then UP-only Exact-2F')
