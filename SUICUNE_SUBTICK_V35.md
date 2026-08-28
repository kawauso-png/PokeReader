# Suicune Deep Probe v3.5 — direct F604 subtick logger

Base: `suicune-deep-probe-v3` @ `47c45ff` (v3.4).

## What changed

The v3.4 same-VBlank differential scan found `0x0022F604` changing `0x25 -> 0x30` between the first and second VBlank rDIV reads. That is +11, exactly matching the 11 LR35902 M-cycles between those reads in Crystal's VBlank RNG sequence.

v3.5 therefore stops running the heavy 64 KiB differential memcpy during ordinary probes and samples one byte directly at every rDIV hook:

- `ASUB`: F604 at 02B5/02B6
- `SSUB`: F604 at 02BD/02BE
- `mcycle`: F604 on every call-log / deep-log rDIV sample

The old `acyc/scyc` columns remain for one transition version, but `asub/ssub` are the new primary timing fields.

## Direct counter interpretation under test

```
M14 = DIV * 64 + F604
A12 = DIV * 16 + (F604 >> 2)
```

One frame is 70224 T-cycles = 17556 M-cycles, so a free-running 14-bit M-cycle counter should advance by:

```
17556 mod 16384 = 1172
```

The two VBlank reads should differ by 11 M-cycles.

## CSV additions

Probe header adds:

- `target_asub,target_ssub`
- `target_a12,target_s12`

Frame section adds:

- `asub,ssub`

Call and deep sections add:

- `mcycle`

The v3.4 `diff_region` section is intentionally omitted from ordinary v3.5 saves.

## Test plan

Take two clean runs under as close to the same Target/operation as practical. Use `analyze_div_subtick.py` on one CSV to validate pair-gap and frame-step behavior; pass two CSVs to compare frame-by-frame jitter sequences.
