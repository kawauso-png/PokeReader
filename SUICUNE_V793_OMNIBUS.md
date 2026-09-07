# Suicune v7.9.3 Audio Omnibus Validator

Base: `suicune-v792-audio-offline-model`

## Purpose

Do not add more timing-sensitive guest reads yet. v7.9.2 already records enough information to test several PRE -> stop1 -> J hypotheses offline from the same trace.

`analyze_suicune_audio_v793.py` accepts one or many irregular PokeReader CSVs and emits:

- `runs.csv`: one row per trial
- `channels.csv`: decoded PRE audio state for Ch1-Ch3
- `pairs.csv`: same-MusicAddress natural experiments
- `hypotheses.csv`: automatic hypothesis checks
- `report.md`: human-readable report

## Run

```bash
python3 analyze_suicune_audio_v793.py celebi_trace_*.csv
```

or:

```bash
python3 analyze_suicune_audio_v793.py ./traces --out ./suicune_v793_report
```

No third-party Python package is required.

## What one trace now tests

The analyzer extracts the dense stop1 same-`rel_adv` cluster, unwraps `sample_live_div/sample_live_sub`, records the raw guest execution amount, decodes `NEUTRALPROBE` J/POST, checks Exact2, decodes the 448-byte `AUDIOPRE` block into Ch1-Ch3 channel structs, finds the first NoteDuration -> ParseMusic crossing window, records SUBROUTINE/LOOP/Vibrato/PitchSlide state, and fingerprints the rel23-rel27 PC route.

For blind testing, the current transport constants are frozen rather than re-fit on every new batch:

- J offset: 3449 M-cycle
- rel26 stop-live baseline: 12940
- rel27 stop-live baseline: 12904

The raw `stop_exec_m` column is always preserved so these calibration constants can later be replaced without losing data.

## Current 0001-0014 sanity result

The current development batch automatically reproduces the important 0005 -> 0006 natural experiment:

- same Ch1/Ch2/Ch3 MusicAddress: `72EB/73FC/74EF`
- NoteDuration: `35/35/35 -> 32/32/32`
- first-Parse crossing count: `0 -> 3`
- stop1 raw guest execution delta: about `+1342 M`
- J delta: `+1339 M`

It also flags 0010 as the main J/gap residual outlier and rejects the coarse hypothesis that merely having `SOUND_SUBROUTINE` set adds a universal ~20 M-cycle cost.

## Next layer

This validator deliberately stops before pretending the reduced audio simulator is complete. The next implementation can plug command-by-command `ParseMusic` / `sound_call` / `sound_ret` / `sound_loop` / Vibrato / UpdateChannels cycle simulation into the already decoded `channels.csv` state, while keeping the same reporting harness and blind-test workflow.
