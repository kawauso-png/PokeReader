# Suicune Observe v3.8

This branch keeps the v3.7 deterministic Suicune execution path unchanged and adds clean C-side host timing observation.

## Purpose

Before implementing Host Phase Lock, measure whether host timing actually explains C / w / AP4 divergence.

v3.8 records timing outside the Deep Probe Rust/trace path so the existing `atick` probe overhead is not the only host-phase instrument.

## Operation

Same as v3.7:

1. Load the same save.
2. Pause at the same Target.
3. Hold physical UP.
4. Tap Y+X.
5. Release Y/X while keeping UP held.
6. Keep UP held comfortably through the exact two Fixed frames.
7. Release UP.
8. Do not press R. Auto-resume is still the v3.7 path.
9. Hands off until result lock / auto-pause.

For the first experiment, collect five full traces from the same save and same Target.

## New CSV section

After the ordinary trace sections, v3.8 appends:

```csv
observe_version,fixed_arm_tick,fixed_release_detect_tick,fixed_start_tick,fixed_first_hook_tick,fixed_end_tick,up_release_detect_tick,resume_command_tick,post_resume_hook_tick,fixed_to_hook_tick,resume_to_hook_tick,host_period_samples,host_period_min,host_period_median,host_period_p99,host_period_max,bench_samples,bench_min_nonzero,bench_median,bench_p99,bench_max,bench_zero,bench_le255,bench_gcd
V38,...
```

### Event definitions

- `fixed_arm_tick`: C-side tick when the v3.8 Suicune path is armed after Y+X with UP held.
- `fixed_release_detect_tick`: clean tick when Y/X/L/R release is observed and the pending Fixed run is allowed to start.
- `fixed_start_tick`: tick immediately before the exact Fixed two-frame run is released.
- `fixed_first_hook_tick`: first top-screen hook tick after Fixed start. This is captured in C before `scan_input()` / Rust `run_frame()`.
- `fixed_end_tick`: first pause-loop tick after the exact Fixed run has completed.
- `up_release_detect_tick`: clean tick when UP/Y/X/L/R are all observed released after the two frames.
- `resume_command_tick`: tick immediately before v3.7 sets `is_paused=false`.
- `post_resume_hook_tick`: first top-screen hook tick after the resume command, captured before the Rust trace path.
- `fixed_to_hook_tick`: `fixed_first_hook_tick - fixed_start_tick`.
- `resume_to_hook_tick`: `post_resume_hook_tick - resume_command_tick`.

The last two are the critical command-to-actual-host-hook latency measurements. Their run-to-run spread matters more than spin-loop accuracy by itself.

## Clean host-period sampling

After `post_resume_hook_tick`, v3.8 collects 128 consecutive top-screen hook intervals in C. This avoids using Deep Probe `atick` as the only LCD / host-frame period estimator.

The CSV records sample count, min, median, p99, and max.

## svcGetSystemTick microbenchmark

On the first Suicune v3.8 arm after plugin load, C directly executes 4096 consecutive `svcGetSystemTick()` calls with normal interrupts enabled. The benchmark is cached and copied into every later trace from that plugin session.

Reported fields:

- sample count
- minimum non-zero delta
- median
- p99
- maximum
- zero-delta count
- count of deltas <= 255 ticks
- GCD of non-zero deltas

The minimum non-zero delta / GCD indicate practical counter granularity. p99/max describe overshoot risk. `<=255` is a useful diagnostic for the approximate one-M-cycle target window, but a value above 255 is not automatically fatal because a future phase-lock implementation can reject a missed window and retry on the next display period while still paused.

## Five-run analysis order

Do not judge success from Family alone.

1. Verify the Target root (`target/state/div/adiv/sdiv/asub/ssub/P4`) is comparable.
2. Compute circular phase from clean C-side ticks using the per-run clean `host_period_median`.
3. Compare `fixed_start` phase, `resume` phase, and their relative phase.
4. Compare `C` as a cheap hidden-phase sensor, not as ground truth.
5. Compare Family / rotation.
6. Compare the full AP4 sequence and record the first divergent rel.
7. Compare final raw DV.

Important: raw absolute ticks from separate runs are not directly comparable. Use modulo-period phase and circular distance.

## Decision for the next version

Host Phase Lock is justified if clean host phase / command-to-hook latency tracks C or AP4 reproducibility. If `resume_to_hook_tick` (or the Fixed equivalent) itself has large uncontrolled run-to-run variance, tightening the spin loop alone will not solve the problem.

If host phase is not sufficient, keep C as an observed error signal and investigate a closed-loop short-run search rather than blind 17k-slot scanning.
