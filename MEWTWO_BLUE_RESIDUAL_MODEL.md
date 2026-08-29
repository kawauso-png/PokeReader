# Japanese VC Blue Mewtwo — residual model v2

This note preserves the real-hardware conclusions from the Mewtwo HUNT work so later builds do not regress to a fresh calibration.

## Keep these results

- Japanese VC Blue title ID: `0004000000170E00`.
- `FFD3/FFD4` are the live Gen I Random Add/Sub bytes used by the project.
- `CFD8/CFD9` are the enemy raw DV bytes.
- The VC backing pointers and HRAM reads were confirmed on hardware.
- The Mewtwo transition detector reached the actual battle.
- The search path reached a predicted shiny candidate (`BAAA`) in a real encounter.
- A one-frame A pulse was unreliable on hardware.
- A **two-frame A hold** was the successful input primitive and is the only input primitive that should be used for the next HUNT implementation.

## Recovered PRED -> ACT validation pairs

| trial | PRED | ACT | byte residual (mod 256) |
|---|---:|---:|---:|
| validation A | `0575` | `1281` | `+0D / +0C` |
| validation B | `1AF9` | `5B3B` | `+41 / +42` |
| validation C | `9FAA` | `BEC8` | `+1F / +1E` |
| shiny target miss | `BAAA` | `4939` | `+8F / +8F` |

All four trials move the two DV bytes by the same modulo-256 amount, within one count. This is much stronger structure than an unconstrained DV miss.

## Primary hypothesis

Before introducing a discrete Random-call shift, model the observed result as

```
ACT_DV1 ~= PRED_DV1 + delta   (mod 256)
ACT_DV2 ~= PRED_DV2 + delta   (mod 256)
```

with an allowed `±1` split between the two bytes from sub-frame rounding.

This shape is consistent with a shared DIV/fine-phase timing error affecting the two adjacent DV Random calls. It is not evidence that the whole target search is random or unusable.

The old `MODEL UNSTABLE` label was therefore too strong. The search successfully delivered a shiny-predicted target; the remaining problem is to determine `delta` from the target/final-A phase and compensate for it.

## Corrected HUNT strategy

1. Keep the existing target search and phase machinery that already reached `BAAA`.
2. Keep final A as an exact **2-frame hold**. Do not fall back to 1F.
3. For every validation encounter, save:
   - target / predicted raw DV,
   - phase immediately before the 2F A run,
   - RNG Add/Sub and DIV before/after the 2F run,
   - actual `CFD8/CFD9`,
   - residual `d1=(ACT1-PRED1)&FF`, `d2=(ACT2-PRED2)&FF`.
4. Classify a run as `COMMON` when `d1==d2`, `COMMON±1` when their circular distance is one, otherwise `NON-UNIFORM`.
5. Correlate common delta against the pre-A/final-A phase. Only after common-delta fails should the implementation search discrete call shifts.
6. Once a phase -> delta mapping is repeatable, apply the correction during shiny search: test `corrected_actual = add_delta(predicted_raw, delta)` for shiny eligibility instead of testing `predicted_raw` directly.

Equivalently, for a calibrated delta the old predictor can search the preimage of each shiny raw DV:

```
predictor_target = shiny_raw - delta  (byte-wise modulo 256)
```

`analyze_mewtwo_residual.py --delta XX` prints these preimages.

## Next hardware test

The highest-value test is not a new broad calibration. Repeat the same operational protocol with 2F A and gather several `PRED -> ACT` results while recording the pre-A phase. Ideally include repeated attempts at one target/phase. We want to answer one narrow question:

> For the same phase and same 2F A protocol, does `delta` repeat (or stay within ±1)?

If yes, the shiny search can be corrected directly. If no, use the saved phase/RNG/DIV tuple to split the residual into a finer phase class before considering call-shift branches.
