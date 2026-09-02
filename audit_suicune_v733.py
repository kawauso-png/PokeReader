#!/usr/bin/env python3
from pathlib import Path

M = Path('3gx/sources/main.c').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()

def need(x,m,label):
    if m not in x: raise SystemExit('v733 missing '+label+': '+m)
def forbid(x,m,label):
    if m in x: raise SystemExit('v733 forbidden '+label+': '+m)

# Proven physical execution protocol stays UP hold -> B tap.
need(M,'(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)','UP+B trigger')
need(M,'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)','B release gate')
need(M,'suicune_auto_resume_pending && !(held & KEY_DUP)','Exact2F UP safety')
need(T,'S732 TEST UP+B','current TEST UI')

# v7.3.3 hardware fix: host_request_resume must clear every C-side state that
# can intercept the next TEST before the UP+B block is reached.
start = M.index('void host_request_resume(void)')
end = M.index('\n}', start) + 2
r = M[start:end]
for marker in [
    'is_paused = false;',
    'fixed_frames_remaining = 0;',
    'fixed_run_pending = false;',
    'fixed_armed = false;',
    'suicune_auto_resume_pending = false;',
    'fixed_a_frames = 2;',
    'fixed_last_run = 0;',
]:
    need(r,marker,'host reset '+marker)
forbid(r,'fixed_run_id = 0;','fixed run ID reset')

# Why this matters: the auto-resume release wait precedes the FastValidate
# UP+B block in the pause loop. Stale auto_resume_pending would otherwise eat
# the next TEST. Keep this ordering assertion so future refactors cannot hide
# the same bug without also updating the reset contract.
auto = M.index('if (suicune_auto_resume_pending)')
btrig = M.index('(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)')
if auto >= btrig:
    raise SystemExit('v733 unexpected pause-loop ordering changed')

# Soft-reset consumer still calls host resume after rebuilding the Rust session,
# and v7.3.2 fresh-session rules remain intact.
need(T,'pnp::request_resume();','soft-reset host resume')
for m in ['S732 RESET WAIT','S732 SCAN','SOFTRESET,V732','GLOBALBEAM,V732',
          'self.soft_reset_expected_tid = reader.trainer_id();',
          'let expected_tid = self.soft_reset_expected_tid;',
          'add_div_tracker().index().is_some()',
          'sub_div_tracker().index().is_some()']:
    need(T,m,'v732 invariant '+m)

print('v7.3.3 AUDIT PASS: UP+B unchanged; soft reset now clears stale C-side auto-resume/armed/pending Exact2F state; v7.3.2 fresh-session logic preserved')
