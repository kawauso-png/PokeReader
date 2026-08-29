# Suicune Prototype v3.9.1 — validation-first

v3.9 is superseded by this validation-first pass.

## Critical fixes

1. The 16-frame DIV increment sum is **293**, not 296.
   - `0x12 * 11 + 0x13 * 5 = 293`
   - `1172 M/frame * 16 / 64 = 293`
2. The old `14/14` self-test was circular: profile X replayed on profile X's own root.
3. The headline test is now leave-one-out (LOO).
4. Distance metrics include phase-normalized DIV-byte errors and first error rel.
5. Branch-envelope LOO reports how many held-out rel positions are not covered by the other runs of the same prototype.

## Regression on traces 0066–0079

- DIV cycle sum: **293**
- self-profile replay sanity: **14/14** (implementation sanity only)
- raw-DV LOO: **0/182**
- same-prototype raw-DV LOO: **0/38**
- exact `(phase_a, phase_s)` coverage: **10/256 = 3.9%**
- diff-class coverage: **2/16 = 12.5%**

Therefore the v3.9 exact-profile shiny candidate search is **not a validated predictor** and must not be treated as production output.

## Branch-envelope LOO highlights

With the held-out run removed, same-prototype donor trajectories are rotation-aligned and normalized by the first DIV-byte offset. The remaining donor values form an observed branch envelope at each rel.

Notable results:

- 0066 A: missing 1/690
- 0073 A: missing 1/690
- 0074 A: missing 1/690
- 0076 A: missing 2/690
- 0078 D: missing 1/689, first missing rel 590

B/C and D-0079 remain substantially less covered.

This supports moving from whole-profile replay toward error-position branch enumeration, but it does not yet validate a production shiny searcher. Prototype/rotation inference and branch coherence must be generated without peeking at the held-out trajectory.

The 3GX remains v3.8 Observe; no plugin replacement is required for this offline validation step.
