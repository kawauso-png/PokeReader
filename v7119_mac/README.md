# S7119 bounded neutral-frame calibration

This is a hardware calibration feature, not a shiny encounter launcher. It accepts only 1–32 neutral display-frame releases, then remains paused. It does not inject UP or change guest RNG, DIV, DV, or save data. A display-frame release is counted at the next bottom-screen pause callback; its relationship to the copied VM's frame function still needs hardware validation.

Enter through the existing shiny search and SELECT stop. Release every physical key. A successful fresh export shows `S7119 MAC SNAPSHOT READY`, creates `mac_state.bin/json`, zeroes `mac_step.req`, and writes `mac_step.json` with `phase=ready`. While Mac mode is enabled, ordinary resume keys cannot release the game. SELECT refreshes the snapshot/request channel; Y+DOWN exits to the existing search when no step is active.

The 128-byte little-endian request format is specified and checked in `protocol.h`. Its nonce must be nonzero, strictly newer than the consumed nonce, and bound to the exported state ID, ADV, seed, and all four hashes. The request deadline must be in the future and at most 30 minutes ahead. Reserved words must be zero; FNV1a protects the first 124 bytes. Cadence 30 or 60 is a minimum wall-clock spacing, not a guarantee of exact emulation FPS.

At acceptance, a fresh BEFORE image is exported as `mac_before.bin/json`. A `started` report must be written successfully before the first release. Each actual release and subsequent pause records its tick, ADV, seed, PC, DIV, native cached keys, RTC inputs, and timing fields. The final state is exported as `mac_state.bin/json`; a `complete` or `aborted` report links both state IDs and the request nonce. Failed preconditions produce `rejected` where SD writes remain possible. A write failure may only be visible on the device's error panel.

Do not retry an uncertain request using a new nonce. Read its status first. Replaying the same consumed nonce never executes more frames. A complete report and both matching snapshots are required before treating a calibration sample as valid. Physical keys pressed during a release can affect the real game before the next pause; that trial is aborted and must not count as neutral validation.

`verify_suicune_mac_step_v7119.py` tests exact bounds 1–32, no duplicate release, stale identity, deadlines, held keys, export/journal failures, JSON capacity, generated integration guards, and snapshot serialization integrity. These software tests do not establish hardware RNG prediction accuracy.

A captured physical neutral state stores `0xFCFF` in the cached key halfword; offline neutral replays use `0xFFFF`. The GB button mask is the low byte (confirmed in the VC joypad routine at `0x195DF4`). Test neutrality of that byte and physical HID separately, while recording the full halfword. Do not reject a real neutral state solely for its upper byte.
