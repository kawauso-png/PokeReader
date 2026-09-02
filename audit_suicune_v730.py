#!/usr/bin/env python3
from pathlib import Path

P=Path('reader_core/src/crystal/practical.rs').read_text()
T=Path('reader_core/src/crystal/trace.rs').read_text()
M=Path('3gx/sources/main.c').read_text()

def need(x,m,label):
    if m not in x: raise SystemExit('v730 missing '+label+': '+m)
def forbid(x,m,label):
    if m in x: raise SystemExit('v730 forbidden '+label+': '+m)

# Current physical protocol is UP hold -> B tap. B is consumed by the pause
# loop and exact VC frames receive UP only. Do not regress to Y+X.
need(M,'(just_pressed & KEY_B) != 0','B trigger')
need(M,'(held & KEY_DUP) != 0','physical UP requirement')
need(M,'suicune_fast_validate_pending','B-release pending gate')
need(M,'exact_up_guard','post-2F UP-release guard')
need(T,'S730 TEST UP+B','correct user instruction')

# Actual-root scan: no sparse PRE gate before global evaluation.
need(T,'fn practical_wait_monitor','live scanner')
s=T.index('fn practical_wait_monitor'); e=T.index('fn practical_fail',s); mon=T[s:e]
need(mon,'for id in 1..=practical::proven_lane_count()','global proven scan')
need(mon,'evaluate_empirical_id','global empirical scan')
need(mon,'practical_global_speculative=true','global TEST marker')
forbid(mon,'proven.is_none()&&!emp{return}','old zero-coverage gate')
need(mon,'let state=reader.rng_state();let div=measured_div();','actual current root')
need(mon,'pnp::request_pause();return','immediate current-root pause')

# Recent UP+B bank coverage. Source0097 stays identifiable but cannot drive a
# shiny target until its observed 241F terminal path is represented.
need(P,'const EMP_COUNT:usize=8','8 recent empirical lanes')
for src in ('source:102','source:103','source:104'):
    need(P,src,'recent donor '+src)
need(P,"pre_proto:b'A',pre_rot:2",'0102 PRE A/r2')
need(P,"pre_proto:b'C',pre_rot:7",'0103 PRE C/r7')
need(P,"pre_proto:b'B',pre_rot:1",'0104 PRE B/r1')
need(P,'source==102||source==103','alternate route4 family selector')
need(P,'source!=97','0097 prediction quarantine')

# rel40 must use the ACTUAL POST and evaluate all same-POST donors. It accepts
# exactly one shiny continuation; zero or ambiguous results fall through LEARN.
need(T,'fn rebind_shiny_post_v730','shiny-filtered rel40 resolver')
s=T.index('fn rebind_shiny_post_v730'); e=T.index('fn enter_stage3_learn',s); rb=T[s:e]
need(rb,'prediction_post(id)','actual POST identity filter')
need(rb,'evaluate_post_exact','all proven POST suffixes')
need(rb,'evaluate_empirical_post','all empirical POST suffixes')
need(rb,'if count!=1{return false}','unique shiny continuation gate')
forbid(rb,'lane_for_post_unique','old identity-unique gate')

# Hard downstream checks remain mandatory.
for m in ('practical_expected40_state','practical_expected716_state','practical_expected717_state'):
    need(T,m,m)
need(T,'GLOBALBEAM,V730','v730 telemetry')
need(T,'FP {}{} N{}','coverage diagnostic')
forbid(T,'S720 ','stale v720 UI')

# The old static future search constants may still exist for historical modes,
# but the v7.3 live monitor itself must not use SEARCH_HORIZON.
forbid(mon,'SEARCH_HORIZON','long-range search in live monitor')

print('v7.3 AUDIT PASS: UP+B preserved; actual-root global beam removes PRE coverage dead-zone; 0102/0103/0104 added; 0097 quarantined; rel40 shiny-only unique rebind; 716/717 guards preserved')
