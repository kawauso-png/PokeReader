#!/usr/bin/env python3
from pathlib import Path

P=Path('3gx/sources/main.c')
s=P.read_text()

old='''        // v6.5.8 FastValidate: hold UP and tap B; no Y/X chord.\n        // B never reaches a VC frame: fixed_run_pending waits for its release.\n        // Require !Y so B cannot overlap the Y-command namespace.\n        if ((just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y))\n        {\n'''
new='''        // v7.2.4 robust diagnostic arm.  In auto-paused probe mode, relying\n        // only on the one-poll `just_pressed` edge can miss B entirely.  Latch\n        // whenever physical UP+B are simultaneously held.  fixed_run_pending\n        // / suicune_auto_resume_pending prevent re-arming after the latch.\n        // B is still consumed: no VC frame is released until B is physically\n        // released, and the Exact-2F window therefore contains UP only.\n        if ((held & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)\n            && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n'''
if s.count(old)!=1:
    raise SystemExit(f'v724 arm block expected 1, got {s.count(old)}')
s=s.replace(old,new,1)

# Keep the user-visible behavior robust: once B has been released and the two
# exact frames have run, UP release is the only condition needed to resume.
# Existing phase locks are retained to preserve donor timing compatibility.
P.write_text(s)
print('Applied Suicune v7.2.4 RobustProbeArm: held UP+B latch replaces fragile just_pressed B edge')
