# Suicune Factor v4.0 Target Search

This is the practical target-search layer for the JP VC Crystal Suicune Exact-3F experiment.

## Real-device inputs

The searcher is intentionally based only on values visible in the current PokeReader UI:

- Advance
- State
- DIV
- ADIV
- SDIV

No AP4/SP4 entry is required.

For validated A13/D13 Exact-3F traces, the hidden target subticks satisfy:

`SSUB = ASUB + 11 (mod 64)`

on 7/7 runs, so the detailed pass enumerates ASUB 0..63 and derives SSUB.

## Root progression

Future target roots are generated with the corrected 16-frame DIV increment pattern:

`12 12 12 13 / 12 12 13 12 / 12 13 12 12 / 13 12 12 13`

The 16-frame sum is 293.

For one normal advance:

1. `aDIV8 += INC[ADIV & 15]`
2. `sDIV8 += INC[SDIV & 15]`
3. increment ADIV/SDIV indices
4. `add += aDIV8`
5. `carry = overflow(add)`
6. `sub -= sDIV8 + carry`

This progression was checked against Trace 0008: Target 8347 (`State=6459`, `DIV=E9E9`, `ADIV=9680`, `SDIV=8967`) advances to 8348 `State=5F5D`, `DIV=FBFB`, matching the trace.

## Search modes

- Balanced: 14 ASUB probes for the coarse scan, then full 64-ASUB evaluation on shortlisted targets.
- Fast: six ASUB values actually observed in validated A13/D13 runs (`03,0D,14,16,2D,35`) for the coarse scan, then full 64-ASUB evaluation.
- Full: all 64 ASUB values on every target; much heavier.

The detailed pass evaluates both validated cells A13 and D13 and all current core factors:

- LOW / MID / HIGH prefix family
- six DV-changing site donor windows
- stop2/tail donor
- route 3 / route 4 deep profiles
- exact deep 2F60/2F68 arithmetic

## Ranking

Candidates are ranked primarily by how many of the six actually observed A13/D13 ASUB values support a shiny result, then by:

- total ASUB support
- number of supported cells
- LOW/MID/HIGH family coverage
- route coverage
- factor support

A candidate is a reachable shiny branch in the current factor model, not a guaranteed DV.

## Real-device workflow

1. Enter current Advance / State / DIV / ADIV / SDIV.
2. Search future targets.
3. Prefer high-ranked candidates.
4. Advance to the listed Target.
5. Before execution, verify the listed State / DIV / ADIV / SDIV match the device display.
6. Run the current Exact-3F UP-gated procedure.
7. Save the resulting trace and feed it back into the model.
