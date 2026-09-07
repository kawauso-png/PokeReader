# Suicune v7.9.6 — Mechanistic J Predictor

This branch deliberately starts from `suicune-v792-audio-offline-model`.
It does **not** inherit the v7.9.5 donor-gate assumptions.

## Current evidence baseline

Development traces 0001..0013:

- all 13 physical-UP Targets are `PREFP A/r13`
- all 13 have `target_div A8A9`
- AUDIOPRE exists for 0004..0013
- 0004 alone has the one-frame-earlier stop1 boundary (`s1=27`); the others use `s1=28`
- 0002 and 0012 independently reproduce the same target/state/J/POST tuple

Mechanistic cycle model for 0004..0013:

```text
AUDIOPRE C100..C2BF + JP VC Crystal ROM
  -> execute bank 3A:$405C (_UpdateSound) s1 times
  -> execute _UpdateSound 6 additional times (SkipMusic(6))
  -> count real LR35902 M-cycles
  -> J_pred = cycles - 7101.9
```

Development performance:

- max absolute J error: 14.1 M-cycle
- mean absolute J error: 5.1 M-cycle
- 6 / 10 runs within +/-2 M-cycle
- K = cycles - J ranges 7093..7116

No regression coefficients are part of this model. `7101.9` is the single additive endpoint constant.

## PRE semantics correction

Do not conflate the two cells:

```text
pre-neutral scan root: historical v7.8.6 A/r10 bucket76
          + neutral 3F
physical-UP Target:    PREFP A/r13
```

The historical statement that the measured physical-UP PRE itself was A/r10 was wrong.
This does not by itself prove that an A/r10 pre-neutral root is invalid; it means the two measurement points must be named separately.

## Runtime target architecture

The final hunt should not exact-match one of 11 AUDIOPRE donors.
Instead:

```text
session start
  -> read AUDIOPRE once while safely paused
  -> identify Ecruteak music phase
  -> track music phase deterministically while natural game frames advance

for each candidate physical-UP Target
  -> derive s1 branch (or propagate both 27/28 if not yet classified)
  -> table lookup / mechanistic lookup for SkipMusic(6) cycle cost
  -> J interval
  -> propagate J candidates through existing POST/rel40/tail model
  -> AutoPause only if shiny remains possible
  -> physical UP only
  -> Exact2 FFA4
  -> M14 resume
```

The hot path must not read 448 bytes every frame.
A 15957-entry precomputed music-cycle table is the intended runtime representation.

## Residual K experiment

Before claiming >20-30% physical-UP success, test whether the remaining K offset is deterministic per target.
Preferred repeat target: target 1885 / state 7A82, because 0002 and 0012 already reproduce J=29 and POST=A/r1, while 0012 has AUDIOPRE.

Collect 2-3 additional truly independent runs with AUDIOPRE and record the prediction **before** physical UP.

- if K repeats: treat it as deterministic endpoint/sample offset and model it
- if K does not repeat: inspect exact CPU timing / ParseMusic data-dependent paths

Do not fit a multi-feature statistical correction to the 10 development runs.

## Inputs still required for the exact runtime table

At least one of the following must be supplied to this branch's build/precompute step:

1. the user's extracted Japanese VC Crystal `rom.gbc`, or
2. the LR35902 emulator + ROM-cycle-table output used to obtain the development cycle counts.

The ROM itself must not be committed to the repository.
Generated compact cycle tables may be committed once produced.

## Safety invariants

Unchanged:

- no RNG write
- no DIV write
- no DV write
- no save write to create shiny
- no synthetic UP
- no Legal Advance
- no R input
- physical UP is passed only by the existing FFA4 Exact2 mechanism
- post-Exact2 resume remains M14
