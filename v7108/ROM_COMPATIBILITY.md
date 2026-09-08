# v7.10.9: captured VC image compatibility

The five v7.10.8 search logs stopped with error 5 before audio simulation or DV ranking. Each reported FNV-1a 57D31952. A complete 2 MiB diagnostic capture was then read locally and its file FNV matched the device report.

| Image | SHA-256 | FNV-1a 32 |
| --- | --- | --- |
| Analysis reference | 136ada06cb68656b7de475fa4b278d37dbeff8f5257e7dfdf7f4a4aec19a90f3 | 6C177283 |
| Captured VC image | 68ef4286568a27fd9b1e9b26ea2ad703afac127dab06cf46ff5afbd51f5a4ecb | 57D31952 |

The images differ at 119 bytes across 16 banks. Bank 3A containing the sound engine is identical. The RNG routine at 2F5E and its inspected surrounding bytes are also identical. Some differences elsewhere replace opcodes with FC, including six locations in bank 23. This does not establish the semantics of those replacements or equivalence of full game/VC timing.

Local validation replayed the existing 40-frame conditional sound calculation with both ROM images and all nine historical PRE snapshots (traces 21–25 and 27–30). For snapshots without IO, both 00 and FF fill variants were checked. Python and the actual C runtime sound interpreter agreed on cycle counts and every byte of the resulting 448-byte sound state for both ROMs. Across these runs, 1,475 unique ROM byte addresses were read; none overlapped the 119 changed bytes.

The runtime now accepts the two verified full-image FNV fingerprints. All other fingerprints still stop before searching and produce diagnostics. The source images are not bundled or uploaded. The predictor continues to read the actual loaded ROM and run in plugin-owned scratch memory. The score model, acceptance threshold, physical UP gate, Exact2 and M14 timing are unchanged.

This fixes compatibility with the captured image. It does not validate shiny success probability or a complete PRE-to-DV game emulator. An untested audio path may still stop at the interpreter's existing unsupported-instruction/read guards.
