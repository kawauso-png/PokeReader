# Suicune Prototype / Rotation v3.9

This branch keeps the v3.8 Observe 3GX behavior unchanged and moves the next experiment into offline analysis/search.

## Model

The current traces 0066-0079 are best described by four 16-step micro-jitter prototypes plus a circular rotation, not by treating every whole trace as a separate family.

Reference cycles:

- A: `1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1`
- B: `-4,7,-3,0,-2,3,-1,2,1,-3,2,-1,-1,3,0,-3`
- C: `-2,1,1,-2,2,0,-1,0,1,-8,7,1,-4,4,0,0`
- D: `2,0,-2,2,-1,-1,-8,9,-1,-4,5,-1,0,-2,3,-1`

Classification uses rel40-55 and chooses the prototype/rotation with maximum exact Hamming score.

On traces 0066-0079:

- 12/14 are 16/16 fingerprint matches.
- 0076 and 0077 are 14/16 near-matches.
- stable regions outside the four local windows are ~95-98% exact per run.
- most mismatches are concentrated in `220-269`, `340-459`, `520-559`, `600-659` plus stop/tail structure.

## Files

- `analyze_suicune_prototype_v39.py`: trace analyzer + exact replay profile generator.
- `build_suicune_prototype_v39.py`: turns the generated model JSON into a standalone browser searcher.
- generated `suicune_shiny_jpvc_prototype_v39.html`: standalone searcher from traces 0066-0079.

## Searcher behavior

Default `OBSERVED exact phase` mode only replays profiles whose:

`phase_a == ADIV & 15` and `phase_s == SDIV & 15`.

This preserves the physical phase gate used by the older tools while presenting disagreement as prototype/rotation branch uncertainty.

`same diff class` is exploratory and intentionally less strict.

The raw-DV replay is algebraically accelerated. Instead of executing ~730 state updates for every profile and target, it precomputes divider contributions and computes the final low state byte from cumulative A/S sums and total carry count.

Known-trace exact replay regression: **14/14** for 0066-0079.

## Current limitation

The searcher currently uses the observed exact branch envelope. The four local windows are identified and hashed by the analyzer, but independent cross-window recombination is not enabled yet because unvalidated recombination can invent impossible trajectories. This is deliberate: first keep 14/14 regression, then factor windows only when additional repeated traces establish compatible branch transitions.
