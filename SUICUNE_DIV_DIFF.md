# Suicune Deep Probe v3.4 — same-VBlank DIV differential probe

This replaces the v3.2 consecutive-frame Wide capture for the next experiment.
The goal is to find emulator state that changes **inside one VBlank RNG update**,
between the first rDIV read (`02B5/02B6`) and the second (`02BD/02BE`).

## Why this experiment

The v3.2 traces proved that the byte immediately after the known rDIV host byte
behaves like another GB I/O register, not a useful hidden DIV low byte.  They
also showed that the old JP cycle hook at `0x1A8360` is not installed
(`E3500000`, return address 0).  Consecutive-frame wide dumps additionally pick
up unrelated fast accumulators, so v3.4 changes the question from "what moves
between frames?" to "what moves during the exact 02B6 -> 02BE interval?".

## v3.4 round A

The build scans exactly one region:

```
0x00220000 - 0x0022FFFF   (64 KiB)
```

At the first `02B6` after a Deep Probe starts it copies that region to a static
buffer.  At the matching `02BE` of the same VBlank it copies the region again,
compares locally, and retains only changed bytes.  The scan then disables
itself; the normal Suicune trace continues until DV/route auto-detection.

The metadata contains `pair_ok`.  Because PokeReader increments its logical
`RNG_ADVANCE` at the first VBlank read, a clean same-VBlank pair appears as
`start_advance -> start_advance+1`; `pair_ok=1` verifies exactly that.

## CSV sections

Near the end of the CSV:

```
diff_region,base,len,valid,completed,pair_ok,...
DIFF,00220000,65536,1,1,1,02B6,02BE,...

diff_index,address,offset,before,after,delta8,before16_le,after16_le,delta16_le,before32_le,after32_le,delta32_le
...
```

`total_changes` is the number of changed bytes in the 64 KiB region.
`stored_changes` is capped at 2048.  `overflow=1` means the changed-byte list was
larger than the retained prefix and the run should be narrowed before drawing a
negative conclusion.

The 16/32-bit views start at each changed byte.  They are not claims about the
actual structure; they are included so the offline analyzer can immediately
recognize a counter whose low byte changed but whose neighbouring bytes did not.

## Analyzer

```
python3 analyze_div_diff.py celebi_trace_XXXX.csv
```

It gives highest weight to a 16-bit value whose visible byte follows
`start_div -> end_div`, then ranks changes near plausible 48 T-cycle / 12
M-cycle increments.  A candidate is still only a candidate until a later
lightweight targeted read reproduces it over multiple runs.

## 3DS operation

The Suicune operation is unchanged:

1. Pause at Target.
2. `Y+X` — arm Deep Probe.
3. `Y+B` — arm Fixed A Frame.
4. Hold Up.
5. Tap `Y+L`.
6. Release Y/L while keeping Up held.
7. After the exact 2 frames finish, release Up.
8. `R` — resume.
9. Hands off until the plugin auto-pauses after locking the Suicune result.

The first pair scan occurs at the beginning of the run.  It intentionally adds
host-side work to that frame, but the emulated LR35902 does not advance while
the hook is executing.  Do not use v3.4 trials as timing-quality production
trials; they are instrumentation runs.

On the RNG page, `Xstored/total` is the differential count.  Example:

```
Probe REC T1234
Ph 5/15 D0 X17/17
```

and after the Suicune result is locked:

```
Probe OK +730 4c
DV 679C D4 X17/17
```

## What to do with the result

For round A, one complete CSV is enough.

- If a strong candidate appears, replace this invasive 64 KiB scan with a tiny
  targeted read around that address and verify it over several runs.
- If there is no convincing candidate and `pair_ok=1`, `overflow=0`, that means
  only that **this 64 KiB region has no convincing persistent subtick state**.
  The next regions are `0x08A30000-0x08A3FFFF`, then
  `0x08A40000-0x08A4FFFF`; it does not prove that the emulator has no
  cycle-accurate state anywhere.
