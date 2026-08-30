# Japanese VC Blue — Mewtwo Auto Trace v7

Target: Japanese 3DS Virtual Console Pokemon Blue (`0004000000170E00`).

## Goal

Keep the real-hardware procedure minimal while recording enough internal state to explain the large A-to-DV timing variance seen in traces 0004-0010.

User procedure remains:

1. Load the same save directly in front of Mewtwo.
2. Press A normally to interact.
3. Advance to the final `ミュー` text.
4. Release A completely.
5. Press A once normally to continue.
6. Release A and do not touch any button until the battle starts.
7. Repeat from the same save.

No pause, L/R, CAL sequence, Trace ARM, or Exact2F is required for calibration traces.

## v7 changes

### Robust final-A capture

v6 depended on the Game Boy `hJoyPressed` A edge. v7 keeps that precise trigger when visible, but also records a host-side physical A edge as a fallback.

- `arm_source=1`: Game Boy A edge was captured and used.
- `arm_source=2`: Exact2F path (kept for later target execution).
- `arm_source=3`: physical A fallback was used because a later game edge was not observed.

The CSV records both `physical_a_seq` and `game_a_seq`, so a missed game edge no longer destroys the run.

### Audio / cry wait observation

The Japanese Red/Blue WRAM layout is sampled directly with no page scan in the critical path:

- `D083` = `wLowHealthAlarm`
- `C02A-C02D` = `wChannelSoundIDs + CHAN5..CHAN8`

`WaitForSoundToFinish` checks CHAN5, CHAN6 and CHAN8. v7 records those bytes every sample and marks the first wait-audio start/end transition after the final trigger.

### Lightweight PC candidates

The two LR35902-PC candidates recovered in the earlier real-hardware Stage 9/10 work are sampled directly:

- host `0x0021B8F8` (`pc_a`)
- host `0x0021B890` (`pc_s`)

v7 intentionally does not run the older 0x100-byte-per-frame scan because instrumentation overhead could perturb DIV timing.

### Longer ring buffer

Trace capacity is increased from 256 to 512 samples so the 200+ frame paths observed in the current Mewtwo data remain fully captured.

### Result display

The old 120-host-frame result gating is removed. When the Mewtwo battle signature is observed and a trace was armed, v7 finalizes/saves the CSV regardless of the A-to-battle distance.

## New CSV fields

Meta adds:

- `physical_a_seq`, `game_a_seq`
- `physical_to_battle`, `game_to_battle`
- `opponent_seq`, `opponent_rel`
- `audio_start_seq`, `audio_start_rel`
- `audio_end_seq`, `audio_end_rel`
- `lowhealth_trigger`, `lowhealth_bit7_seen`
- PC candidate host addresses

Per-sample rows add:

- `phys_keys`, `phys_a`
- `low_health`
- `snd5`, `snd6`, `snd7`, `snd8`
- `pc_a`, `pc_s`
- marker columns for physical/game A, opponent, audio start/end, DV write and battle.

## What to collect next

Start with 3-5 v7 traces using only the minimal procedure above. The first analysis should answer:

1. Does the physical fallback eliminate the v6 0006-style wrong A anchor?
2. Do short and long A-to-DV paths correlate with `wLowHealthAlarm` bit 7?
3. Do `snd5/snd6/snd8` show a clean cry-wait interval whose length explains the variable section?
4. Does either PC candidate produce stable phase markers around audio end / DV write?

Only after those questions are resolved should prediction/autopause logic be added.
