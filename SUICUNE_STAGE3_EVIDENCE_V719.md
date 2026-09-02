# Suicune Stage3 v7.1.9 — hardware evidence and production policy

## Conclusion

The current architecture is mechanically capable of precise Exact-2F execution and the late Suicune event geometry is highly stable, but the old production READY rule was too optimistic.

A PRE fingerprint does **not** uniquely determine the actual rel40 branch. Therefore a shiny forecast from one donor lane is not sufficient evidence for production READY.

v7.1.9 keeps actual-root scanning and changes only the evidence policy used to decide whether a current root is safe enough to expose as READY.

## What the trace corpus supports strongly

Across the 12 complete traces currently rechecked in the working corpus (0092–0095 and 0097–0104):

- 12/12 satisfy `DV offset = stop2 offset + 13`.
- 8/12 use `stop2 +717 -> DV +730`.
- 4/12 use `stop2 +718 -> DV +731`.
- route3 and route4 both occur, but neither breaks the +13 endpoint relation.

This supports keeping the existing endpoint/716/717 machinery.

The recent practical traces also show that the UP+B command is not the dominant failure source: the Exact-2F window contains UP on rel0 and rel1, followed by no key on rel2 in the checked failures.

## What the corpus disproves

The following PRE cells have produced an actual rel40 POST different from at least one runtime donor path:

| PRE | Registered runtime POST(s) | Additional actual POST(s) observed | Evidence |
| --- | --- | --- | --- |
| A/r3 | B/r8 | A/r12 | 0122 |
| A/r10 | B/r9, C/r8 | A/r2, B/r14, D/r2, D/r15 | 0080, 0088–0091, 0098, 0121 |
| B/r11 | D/r2, C/r2 | A/r2, C/r3, D/r13 | 0093–0100 family |
| D/r12 | C/r2 | A/r2 | 0099, 0120 |
| B/r1 | A/r2 | B/r9 | 0092, 0104 |

Therefore PRE->POST must not be treated as one-to-one.

## Recent false READY regression set

The practical READY failures currently represented in the regression audit are:

- 0080 A/r10 -> D/r15
- 0088 A/r10 -> A/r2
- 0089 A/r10 -> B/r14
- 0090 A/r10 -> D/r2
- 0091 A/r10 -> B/r9
- 0092 B/r1 -> B/r9
- 0093 B/r11 -> A/r2
- 0094 B/r11 -> D/r13
- 0095 B/r11 -> C/r3
- 0120 D/r12 -> A/r2
- 0121 A/r10 -> A/r2
- 0122 A/r3 -> A/r12

All twelve are production-blocked by v7.1.9's Evidence Gate.

In particular, complete traces 0092–0095 reached the final DV but did not preserve the READY shiny forecast:

| Trace | READY forecast | actual DV |
| --- | --- | --- |
| 0092 | 7AAA | 7F89 |
| 0093 | EAAA | 5B1B |
| 0094 | EAAA | 6225 |
| 0095 | AAAA | 6B84 |

LEARN therefore remains diagnostic only. A completed LEARN encounter is useful as a donor/path observation; it is not evidence that the original READY shiny forecast survived.

## v7.1.9 production policy

1. Continue to inspect the actual current root only. No future-target queue or open-loop transport is reintroduced.
2. Evaluate the full current state, measured DIV and full Add/Sub DivTracker indices.
3. If the PRE belongs to a hardware-confirmed branch-conflicted family, do not expose a production READY even if a donor lane predicts shiny.
4. If more than one donor model is registered for a non-conflicted PRE, all known models must predict shiny before READY.
5. At rel40, measured actual state/POST still has authority over the initial forecast.
6. A supported alternate POST may be CrossBranch-rebound only if the measured rel40 suffix itself still predicts shiny.
7. An unsupported valid POST enters LEARN only.
8. rel716/rel717 guards remain mandatory for a production path.

## What is still unproven

There is not yet a hardware trace demonstrating the complete modern production chain:

`S719 READY -> UP+B Exact2F -> valid rel40 production path -> 716/717 guards -> shiny DV`

Therefore v7.1.9 should be described as a stricter, evidence-driven candidate selector, not as a proven guaranteed shiny tool.

The next decisive evidence is a small set of v7.1.9 READY traces. A successful trace would validate the production chain; a rel40 mismatch on one of the currently non-conflicted PRE families would immediately move that PRE into the conflict blocklist rather than being rationalized as random bad luck.
