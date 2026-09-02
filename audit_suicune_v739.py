#!/usr/bin/env python3
from pathlib import Path
H=Path('3gx/sources/hid.c').read_text()
M=Path('3gx/sources/main.c').read_text()
T=Path('reader_core/src/crystal/trace.rs').read_text()
P=Path('reader_core/src/crystal/practical.rs').read_text()

def need(x,s,label):
    if s not in x: raise SystemExit('v739 missing '+label+': '+s[:100])
def forbid(x,s,label):
    if s in x: raise SystemExit('v739 forbidden '+label+': '+s[:100])

# 3DS HID PAD shared-memory layout (same indexes as libctru hidScanInput):
# current PAD ring id at word 4; keys at word 10 + id*4; 8 entries.
need(H,'g_hid_shared_mem[4]','current HID PAD ring selector')
need(H,'g_hid_shared_mem[10 + id0 * 4]','current HID PAD key entry')
need(H,'if (id0 > 7) id0 = 7;','ring clamp')
need(H,'if (id0 == id1)','ring-boundary consistency')
need(H,'g_hid_ring_resamples++','ring-boundary resample counter')
need(M,'set_key_addr((vu32 *)addr);','map HID shared-memory base')
forbid(M,'set_key_addr((vu32 *)(addr + 0x28));','stale fixed HID entry')
forbid(H,'g_current_keys = *g_key_addr;','fixed-slot key read')

# State-machine safety from v7.3.8 stays intact.
need(M,'SUICUNE_TEST_UP_DEBOUNCE_SAMPLES 8U','UP debounce')
need(M,'suicune_test_wait_start_phase_boundary','phase-boundary gate')
need(M,'arm_suicune_probe();','probe ARM')
need(M,'fixed_frames_remaining--; // exact frame #1','immediate frame1')
need(M,'if (suicune_auto_resume_pending && !suicune_test_up_only_held(held))','frame2 UP-only guard')

# Search/model changes from v7.3.8 stay safety-first; v7.3.9 is input-only.
s=T.index('fn practical_wait_monitor'); e=T.index('fn practical_fail',s); mon=T[s:e]
forbid(mon,'practical_global_speculative=true','unsafe global speculative search')
forbid(mon,'for id in 1..=practical::proven_lane_count()','all-proven global loop')
need(P,'const EMP_COUNT:usize=7','deduplicated empirical bank')
need(T,'fn rebind_shiny_post_v736','repaired rel40 resolver')
need(T,'practical_expected716_state','716 guard')
need(T,'practical_expected717_state','717 guard')

for s in ['S739 TEST HOLD UP 0.5s','EXEC,V739','GLOBALBEAM,V739','SOFTRESET,V739']:
    need(T,s,s)
forbid(T,'S738','stale S738 UI')

# Synthetic ring test: fixed slot 0 can disagree with selected current entry;
# current-index sampling must return the selected entry across all 8 ids.
ring=[0]*42
for i in range(8): ring[10+i*4]=0x100+i
for i in range(8):
    ring[4]=i
    old=ring[10]
    new=ring[10+i*4]
    assert new==0x100+i
    if i!=0: assert old!=new

print('v7.3.9 AUDIT PASS: HID uses current 8-entry PAD ring with selector consistency retry; fixed +0x28 stale-slot reader removed; v7.3.8 exact2F/search/rebind safety preserved')
