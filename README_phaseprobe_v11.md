# JP VC Blue Mewtwo heap phase probe v11

Trace 0037 ruled out the static 0x0021B500-0x0021B8FF window as a direct M-cycle subphase source. The live emulator pointers in that trace were:

- DIV pointer: 0x088B2C74
- HRAM base: 0x088B2CF0
- WRAM base: 0x088AEBA0

v11 therefore keeps the same bounded 16-snapshot read-only probe but relocates its 1 KiB window to 0x088B2C00-0x088B2FFF, covering the live DIV/HRAM page. Probe data remains observation-only and cannot affect prediction, pause, search, or input control.
