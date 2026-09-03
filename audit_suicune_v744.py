#!/usr/bin/env python3
from pathlib import Path

# Keep the build workflow compact: normalize the generated BENCH formatter
# immediately before auditing/compiling it.
fix=Path('fix_suicune_v744_csv_format.py').read_text()
exec(compile(fix,'fix_suicune_v744_csv_format.py','exec'),globals())

t=Path('reader_core/src/crystal/trace.rs').read_text()
m=Path('3gx/sources/main.c').read_text()

def need(x,msg):
    if not x: raise SystemExit('v744 audit FAIL: '+msg)

need('bench_phase: u8' in t and 'bench_adv_delta: u32' in t,'benchmark state missing')
need('const WARM:u64=2*TPS;' in t and 'const MEASURE:u64=10*TPS;' in t,'2s/10s timing missing')
need('self.bench_adv_delta=cur.wrapping_sub(self.bench_start_advance);' in t,'advance delta measurement missing')
need('self.bench_a10_count=self.bench_a10_count.saturating_add(1);' in t,'A/r10 counter missing')
need('daa%16==0' in t and '37u32.wrapping_mul(daa/16)' in t,'generalized +16/+37 recurrence audit missing')
need('legal_benchmark,version,tag' in t and 'BENCH,V744' in t,'benchmark CSV missing')
need('S744 LEGAL SPEED' in t and 'S744 BENCH DONE' in t,'benchmark UI missing')
need('pnp::request_pause();' in t,'automatic completion pause missing')
need('pre_vblank_timing_capture_stop();' in t,'capture stop missing')
need('just_pressed & (KEY_DDOWN | KEY_DUP | KEY_DLEFT | KEY_DRIGHT)' in m,'four physical benchmark launch modes missing')
need('suicune_phase_slot = 12U' in m and 'suicune_phase_slot = 15U' in m,'benchmark tags missing')
need('is_paused = false;' in m[m.index('just_pressed & (KEY_DDOWN | KEY_DUP | KEY_DLEFT | KEY_DRIGHT)'):],'benchmark launch does not resume VC')
# Policy boundary for this diagnostic: the v744 patch adds no game-memory write
# and no synthetic key-state setter. Ordinary physical keys are only observed.
patch=Path('apply_suicune_legal_advance_benchmark_v744.py').read_text()
need('host_write_mem(' not in patch,'benchmark patch writes game memory')
need('set_current_keys(' not in patch,'benchmark patch sets synthetic key state')
print('v7.4.4 audit PASS: physical-input-only 2s warmup + 10s ADV/A10 speed benchmark, auto CSV/pause')
