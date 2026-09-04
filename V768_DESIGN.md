# Suicune v7.6.8 Integrated Natural Exact2F Shiny Probe

## Scope

Allowed only:
- observe RNG/State/DIV/PC/F604/Joypad state
- Pause/Resume
- let exactly N natural VC frames execute while the user physically holds UP
- controlled resume timing

Forbidden and not used by v7.6.8:
- RNG state write
- DIV write
- DV write
- save rewrite
- GB joypad RAM write
- rJOYP return/address substitution
- synthetic UP generation
- HID shared-key masking

## One-run flow

1. `Y+DOWN` starts the existing A/r10 bucket76 root scan.
2. Auto-pause on the selected frozen root.
3. Press `B` only to arm the measured root; release B.
4. Hold physical `UP` only.
5. Existing paused single-frame scheduler lets exactly 2 VC frames run.
6. Tool freezes again. Release UP. Controlled auto-resume follows.
7. First 8 running advances only: record host keys + JP Crystal FFA2..FFA9 and first rJOYP timing samples.
8. Around rel27: existing read-only early/J telemetry remains active; early control itself remains OFF.
9. At rel40: classify actual POST and read actual State/DIV.
10. Validate Exact2F using Crystal FFA8. If invalid, save+pause with miss 15.
11. Run actual rel40 inverse tail gate. If no shiny model, save+pause with miss 14.
12. If a shiny model survives, rebind to actual POST/State/DIV and continue naturally.
13. Verify rel716 and rel717 against the rebound model.
14. Detect stop2, preserve the existing +13 DV endpoint model, and let the game generate Suicune normally.
15. On real DV visibility, auto-save CSV and pause.

## CSV highlights

- `JOYFRAME,V768`: first 8 running advances, host + FFA2..FFA9
- `RJOYFRAME,V768`: first rJOYP sample per advance, bounded to 8
- `EARLY,V61C`: J/early phase telemetry
- `REL40GATE,V763`: actual rel40 State/DIV/POST inverse gate
- `endpoint`: stop2 / expected DV
- `probe`: actual raw DV/route when reached
- `INTEGRATED,V768`: compact one-line verdict
