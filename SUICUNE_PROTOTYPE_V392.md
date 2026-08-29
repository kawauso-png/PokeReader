# Suicune Prototype × Rotation v3.9.2

- DIV cycle sum is derived from INC and equals 293.
- Raw-DV leave-one-out remains 0/182; prediction search stays disabled/unvalidated.
- Validation key is now `(prototype, rotation)` rather than prototype alone.
- Strict same-key LOO is reported with missing truth sites, branch sites, enumeration log10, best donor DIV-byte errors, first error rel, standard precision, and recall.

Current groups:
- A r0: 0066, 0073
- A r1: 0068, 0074, 0076
- B r0: 0067
- B r5: 0077
- B r8: 0071
- C r0: 0069
- C r1: 0075
- C r15: 0072
- D r0: 0070
- D r1: 0078
- D r14: 0079

Strict A r1 LOO already shows rotation is necessary but not sufficient:
- 0068: missing 19, branch sites 5
- 0074: missing 1, branch sites 23, precision 17.4%, recall 80.0%
- 0076: missing 4, branch sites 20

Collection priority at Target 6600 with the same original save and v3.8 Observe:
1. Add two D r1 runs (to make n=3).
2. Add one A r0 run (to make n=3).
3. Add A r1 runs to split the 0068-like vs 0074/0076-like sub-branches.
