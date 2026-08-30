# Suicune Endpoint Probe v4.1

Purpose: validate the late-endpoint model without changing the stable v3.8 branch.

## Build base

The workflow keeps the proven execution stack:

1. `apply_suicune_deterministic_v37.sh` — one-trigger Exact 2F, UP held, automatic resume.
2. `apply_suicune_observe_v38.sh` — v3.8 observer/timing CSV.
3. `apply_suicune_observe_v38_post.sh` — benchmark kept outside the execution path.
4. `apply_suicune_endpoint_v41.py` — endpoint-only addition.

Artifact: `PokeReader-Suicune-Endpoint-v41/default.3gx`.

## Endpoint rule

This mirrors `analyze_suicune_factor_v40.py`:

- collapse consecutive equal `advance` values;
- `stop2` is the first repeated advance whose offset from the frozen Target is `> 600`;
- existing traces show `DV advance = stop2 + 13`;
- v4.1 captures at `stop2 + 11`, i.e. expected `DV - 2`.

A guard rejects repeated advances later than `+760` so a failed/mis-armed run cannot treat the encounter result itself as stop2.

## Test procedure

Use the same save/entry method already used by v3.8. Target number itself does not need to be fixed.

At the chosen Target:

1. Pause as usual.
2. Hold physical UP first.
3. While continuing to hold UP, tap `Y+X` once.
4. Exact 2F runs and the normal v3.8 automatic resume path continues.
5. Do not press anything after releasing UP.
6. Near the end of the encounter animation, v4.1 should automatically pause at the detected endpoint (`DV-2`).

On the RNG page the endpoint lines are:

- `EP S+... P+...` after stop2 is detected and before the endpoint is reached;
- `EP +... S....` after the endpoint snapshot has been captured;
- `EP D.... xx/xx` for DIV and A/S subticks at capture.

To finish the validation run, resume from the endpoint pause with the normal plugin resume control and otherwise give no game input. The existing Suicune result detector should then lock the actual DV, save the trace, and pause again after the result.

## CSV addition

The existing `probe` header is unchanged so v3/v4 parsers continue to work. A new section is inserted before the frame table:

`endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys`

For a successful endpoint capture, verify first:

- `status = OK`
- `capture_advance == pause_advance`
- final probe `dv_advance == expected_dv_advance`
- therefore `dv_advance - capture_advance == 2`

Only after that invariant is confirmed should a DV predictor/manipulator be added to the 3GX.
