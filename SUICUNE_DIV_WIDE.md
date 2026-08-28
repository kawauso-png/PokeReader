# Suicune Deep Probe v3.2 — DIV wide capture

This diagnostic build keeps the v3.1 input-release gate, delayed DV detector,
probe summary, and host-tick logging, then adds a short-lived DIV-state capture.

## What is captured

For the first eight VBlank-A rDIV reads after a Y+X Suicune probe starts:

- `0x22F400..0x22F7FF` (1024 bytes) of emulator context
- the resolved host rDIV byte pointer already used by `Gen2Reader`
- 512 bytes around that pointer (`ptr - 0x100 .. ptr + 0xFF`)
- visible rDIV, RNG advance, PC, and ARM11 host tick
- the original instruction at the legacy cycle-hook site (`0x1A8360`)
- the hook macro's resolved return address

Only eight wide samples are collected.  After that the wide capture turns itself
off; normal Deep/Call logging continues.

## On-screen confirmation

On RNG:

- `Ph a/s Dn Wm` — `W` should reach 8

On Trace:

- `calls ... d... w8`
- `cyc XXXXXXXX`
- `CH WWWWWWWW RRRRRRRR`

If the top byte of `CH`'s first word is not `EB` and `R` is zero, the existing
`update_cycle_counter = 0x1A8360` hook is not a valid BL site in this runtime.
No alternate hook address is guessed or patched by v3.2.

## CSV

A final section is appended:

`wide_index,pc,advance,div,host_tick,div_ptr,ctx_base,ctx_valid,ctx_bytes,near_base,near_valid,near_bytes,cyc_hook_word,cyc_hook_ret`

The 1 KiB/512 B blobs are streamed while saving; they do not use a >2 KiB stack
formatter.

## Offline search

Run:

```bash
python3 analyze_div_wide.py celebi_trace_XXXX.csv
```

The analyzer searches for a 16-bit counter whose high byte equals the observed
DIV and whose full value advances by `0x1250` per RNG advance (70224 mod 65536),
with a relaxed `+0x50` low-byte fallback and nearby split-field search.

One successful v3.2 CSV with `W8` is enough for the first pass.  Once the low
byte address is uniquely identified, the next build can replace diagnostic wide
capture with lightweight per-VBlank `asub/ssub` recording.
