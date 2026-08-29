# Japanese VC Blue — Mewtwo CLEAN CAL v1

Target: Japanese 3DS Virtual Console **Pokemon Blue** (`0004000000170E00`).

## Purpose

This branch deliberately removes the mixed Crystal/Celebi/Suicune timing ideas from the Mewtwo experiment.

CLEAN CAL v1 does **not** use:

- Fixed A Frame
- L/R pause or single-frame execution
- phase/bucket prediction
- hJoyPressed edge latches
- automatic shiny search
- automatic pause
- Suicune/Celebi Random-call timing models

The only job of this build is to make one clean measurement pair:

**last physical A press before the Mewtwo battle -> Mewtwo DV result**.

## Confirmed Japanese Blue addresses used

- `FFD3` = hRandomAdd
- `FFD4` = hRandomSub
- `FFD5` = hFrameCounter
- `FF04` = rDIV (via the confirmed VC host backing pointer)
- `D034 == 01` = battle active
- `D036 == 83` = opponent is Mewtwo
- `CFCC == 83` = enemy species is Mewtwo
- `CFD8` = enemy Atk/Def DV byte
- `CFD9` = enemy Spe/Spc DV byte
- `CFDA == 70` = Mewtwo level

Host-side VC backing state:

- WRAM backing pointer slot: `0x0022F6C8`
- HRAM backing pointer slot: `0x0022F6D8`
- rDIV pointer slot: `0x0022F794`
- LR35902 PC: `0x0022F5FC`

## How CLEAN CAL works

Every normal physical A edge is observed by the 3DS host input layer. Outside battle, the plugin keeps only the **most recent A edge** and snapshots:

- Host frame
- RNG Add/Sub
- hFrameCounter
- rDIV
- PC

When the plugin sees the Mewtwo battle signature (`D034=01`, `D036=83`, `CFCC=83`, `CFDA=70`), it locks the battle snapshot and the raw DV from `CFD8/CFD9`.

If the most recent A was within 120 host frames, it is paired with the battle result. This means the first A used to interact with Mewtwo is harmless: the A that dismisses the Mewtwo text is newer and automatically replaces it.

## Real-hardware procedure

1. Install the artifact as:
   `sd:/luma/plugins/0004000000170E00/default.3gx`
2. Start from a normal save directly in front of Mewtwo.
3. Use normal short A presses only.
4. Press A to interact with Mewtwo.
5. When the Mewtwo text is displayed, press A once normally to continue.
6. Do not hold A. Do not press L/R. Do not pause. After the final A, keep hands off until the battle appears.
7. The overlay should lock a `RESULT RAW xxxx` screen. Take/send that screen.
8. Soft-reset/reload the same save and repeat for the next sample.

No startup L sequence is required.

## Result fields

- `A ...` = snapshot at the last physical A edge before battle
- `B ...` = snapshot when the Mewtwo battle signature first became valid
- `Delta H` = host-frame distance from A to battle
- `Delta F` = wrapping `hFrameCounter` distance from A to battle
- `RESULT RAW` = `CFD8:CFD9`

The build also decodes shiny eligibility using the Gen I -> Gen II/Transporter rule:

- Def = 10
- Spe = 10
- Spc = 10
- Atk in {2,3,6,7,10,11,14,15}

## Next step after data collection

Collect several clean A->battle->DV samples under the same save/start position. Only after that dataset is stable do we add future DV prediction and target/autopause logic. The old `Ph255 / Bucket FF` state is intentionally not part of this calibration path.
