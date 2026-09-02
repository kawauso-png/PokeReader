# Suicune v7.2.0 BranchPhase Probe

Diagnostic-only build to isolate the unresolved PRE→POST branch variable.

- `Y+DOWN` scans actual roots only.
- It pauses at the next exact `A/r10` PRE cell, regardless of shiny forecast.
- At `S720 PROBE A/r10`, use the normal physical `UP+B` Exact-2F procedure.
- The encounter is a donor/phase sample, not a shiny attempt.
- Existing V38/SPH/RPH/EARLY/PREFP/POSTFP telemetry is preserved.
- New `BRPHASE,V720` rows save the 17 pre-VBlank host A ticks plus A→A and A→B deltas.
- The rDIV hook uses the already-sampled `host_tick`; v7.2 adds static stores only and no new hot-path timing/emulator reads.

The first goal is repeated A/r10 samples so A/r2, B/r9, C/r8, B/r14, D/r2 and D/r15 outcomes can be compared against host scheduling phase.
