# Suicune Deterministic Execute v3.7

Base: `suicune-deep-probe-v3` / Suicune direct phase collector v3.6.

## Goal

Remove the human `R` resume press from the Suicune timing path before adding Early Profile Gate.

The current v3.6 operation still leaves two human timing points after Target pause:

- release of `UP` after the exact 2-frame window
- `R` resume

v3.7 keeps the real physical `UP` input, but makes the exact window and resume plugin-controlled.

## Operation

At the desired Target:

1. Pause as usual.
2. Hold `UP`.
3. Tap `Y+X` once.
4. Release `Y` and `X`, but keep holding `UP`.
5. Keep `UP` held for a comfortable moment (for example about 0.2-0.5 s). The game only advances for the exact two frames and is frozen again after them.
6. Release `UP`.
7. Do not press `R`. The plugin resumes automatically.
8. Hands off until the existing Suicune Deep Probe locks the result and auto-pauses.

`Y+X` without `UP` held preserves the old behavior: it only arms Suicune Deep Probe.

## Safety behavior

- No exact game frame is allowed through while `Y/X/L/R` are still physically held.
- `UP` must be present for every exact Suicune frame.
- If `UP` disappears too early, the plugin stops allowing further fixed frames and remains paused instead of silently continuing a contaminated trial.
- Manual resume still works outside the automatic execute path.

## Why this version comes before Early Gate

The next question is repeatability, not another larger profile table.

Take repeated runs from the same nominal Target/root with this v3.7 build. If the timing profile becomes strongly repeatable, target-specific/profile-specific shiny search becomes much more valuable. If it still branches, v3.8 should add a host-phase slot selector and Early Profile Gate.

## First experiment

Use one convenient non-shiny Target/root and repeat **6 clean runs** without changing the nominal root.

Record for each run:

- offset
- route
- raw DV
- target P4 / ASUB
- stop1 extra M
- micro-jitter fingerprint

Interpretation:

- 5-6 / 6 same profile: proceed to profile-specific shiny targeting.
- 3-4 / 6 same profile: add Early Gate, but keep the dominant profile as first target.
- 0-2 / 6 same profile: implement host-phase slot control before spending more time on shiny attempts.

## Build

The branch contains `patch_suicune_deterministic_v37.py` plus a dedicated GitHub Actions workflow.

The workflow patches `3gx/sources/main.c` in the build workspace and uploads:

`PokeReader-Suicune-Deterministic-v37`

Use the `default.3gx` inside that artifact. Back up the currently installed plugin before replacing it.
