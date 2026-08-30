# Suicune rel27 branch model v4.0

This branch keeps the physical v3.8 / Exact-3F plugin behavior unchanged and moves rel27 uncertainty reduction into offline analysis.

## Dataset

Current Exact-3F runs: `0006` through `0020` (15 unique runs).

Observed stop1 branch jumps cover multiple trajectories, so rel27 must not be modeled as one fixed path.

## Ranker

For each candidate execution, historical rel27 branch centres are ranked from three circular features that are known by Y+X arm time:

1. `arm_phase = (fixed_arm_tick - target_atick) mod 4,481,151`
2. `Target mod 256`
3. `target_ap4 mod 64`

Each feature is mapped to `(sin(theta), cos(theta))`, then ranked by Euclidean distance in the resulting 6-D space.

Current conservative envelope:

- keep top **4** historical branch centres;
- enumerate **±255 M-cycles** around each centre;
- retain observed A/S stop skew (`sJ-aJ` currently `0`, `-4`, or `-8`).

`4,481,151` is a fixed training reference derived from the robust normal `atick` frame period, not the v3.8 `host_period_median` field.

## Validation

### Branch-centre LOO

On all 15 Exact-3F runs, the held-out observed `J_A` is within ±255 M-cycles of at least one of the top-4 ranked donor centres:

**15 / 15 PASS**

Worst held-out nearest difference: **245 M-cycles**.

This is why the operational width remains ±255 instead of narrowing further.

### Full stop-window LOO

For repeated same-cell groups, the held-out run is removed from both branch-centre donors and same-cell post-stop trajectories. The model enumerates rel27 and then carries the donor rel28-30 trajectory forward, requiring exact equality of `(state, AP4, SP4)`.

Current repeated groups:

- Ac13: `0008`, `0012`, `0013`, `0018`
- Dc13: `0010`, `0016`, `0019`

Result:

**7 / 7 PASS**

With top-4 branch ranking, average rel31 candidate size across these seven held-outs:

- distinct RNG states: **237.6**
- distinct `(state, AP4, SP4)` tuples: **5230.3**

Using every historical branch centre instead produced about:

- **365.9** distinct RNG states
- **8134.0** full tuples

So the v4.0 ranker cuts the rel27 envelope by roughly **35%** while preserving current held-out coverage.

## Important interpretation

Target-only fields are not sufficient to identify one rel27 trajectory. The strongest new signal is the timing phase of the actual Y+X arm relative to the frozen Target hook.

That means the practical next step is not to pretend rel27 is deterministic. The searcher should carry the top-ranked branch envelope, and a later experiment can test whether snapping the Exact-3F start to a controlled host-tick phase reduces the envelope further.

## Tool

`analyze_suicune_rel27_v40.py`

The script filters Exact-3F traces, performs v3.9 prototype/rotation classification, extracts stop1 `J`, and runs the top-K/width branch-centre LOO regression.
