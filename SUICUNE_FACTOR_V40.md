# Suicune Factor v4.0 — Exact-3F factor search

This branch is an offline analysis/search experiment. The v3.8 Observe/UP-gate 3GX remains the physical plugin baseline.

## Dataset

Current Exact-3F unique traces: `0006` through `0022` (17 runs).

Cell counts after corrected frame-index convention:

- A13: 4
- D13: 3
- C13: 2
- C14/D10/D14/A10/A4/A2/C10/A3: 1 each

Validated factor cells for the first core searcher: **A13 and D13**.

## rel40 branch baseline

Using the cumulative P4 correction after stop1, at rel40 the 17 runs separate into three families:

- LOW: about `-502 .. +29 M`
- MID: about `+485 .. +875 M`
- HIGH: about `+1349 .. +1598 M`

A13 and D13 both have current Exact-3F observations spanning LOW/MID/HIGH.

## Factorization

The core path is factored as:

`cell × branch prefix × neutral carrier × 6 changing sites × stop2/tail × deep route`

Changing site windows:

- 217–273
- 290–291
- 339–377
- 387–456
- 521–567
- 602–657

Deep is taken from the observed paired `2F60` / `2F68` rows. Route3 and route4 profiles are both retained.

Normal RNG updates are algebraically collapsed using:

- final add = `(add0 + ΣaDIV) mod 256`
- carry count = `floor((add0 + ΣaDIV) / 256)`
- final sub = `(sub0 - ΣsDIV - carry_count) mod 256`

so independent site recombination does not require replaying ~730 state updates for every combination.

## Validation status

- Exact self replay on current A13/D13 runs: **7/7 truth raw DV included** when the full current model is used.
- Strict held-out Target-root LOO with only observed branch centers: **0/7**.
  - This is expected from the already-observed rel27/stop1 local phase width.
- The earlier stop-boundary envelope test using observed branch centers ±255 M covers the A13/D13 held-out boundary tests, but using that whole envelope as a production search mode creates too many raw-DV possibilities.

Therefore v4.0 separates:

1. **CORE** — observed branch centers, for practical candidate ranking.
2. **ENVELOPE** — ±255 M local branch width, for coverage auditing only.

## Current candidate width

On the seven known A13/D13 roots, CORE produces approximately:

- A13: 1,116–1,280 unique raw-DV candidates
- D13: 339–551 unique raw-DV candidates

This is much narrower than the full envelope and is usable as an experimental reachability filter, but it is not yet a deterministic predictor.

## First experimental shiny reachability result

Known Target **8347** (A13 / LOW) had measured raw DV `65A3`, but CORE also contains shiny raw DV **`6AAA`**.

One explicit factor witness is:

- prefix: trace `0009` (LOW)
- carrier: `0013`
- six site donors: `0008, 0008, 0013, 0008, 0013, 0018`
- tail: `0008`
- deep: `0008` (route4)
- predicted pre-deep state: `3694`
- normal DIV at deep advance: `FE/FE`
- predicted raw DV: `6AAA`

This is an **experimental reachability candidate**, not a claim that repeating Target 8347 will deterministically produce shiny. It is useful as the first real-device test of the factor model.

## Files

- `analyze_suicune_factor_v40.py` — model builder + one-Target CORE evaluator.

Next validation target: collect the outcome distribution from repeating a CORE-shiny Target and compare observed branch/site/deep paths with the factor witnesses.
