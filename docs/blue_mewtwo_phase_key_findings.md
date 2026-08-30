# Blue Mewtwo 0011-0025 phase-key findings

Confirmed on traces 0011-0025:

- GB-side A release -> Mewtwo DV write: 9 sampled frames in 15/15.
- v7.3.2 post-battle phase classes remain in {+90,+91,+94}.
- 0023=+90, 0024=+91, 0025=+91.
- The visible rDIV +18/+19 history can infer a 16-way hidden divider phase bin from a long valid suffix; the release-time (hFrameCounter, bin) pairs had no conflicting phase labels in these 15 traces.
- A shared 8-frame hRandomAdd forward template predicts the final-pre Add within +/-3 in all 15 traces.
- The remaining error is consistent with missing sub-frame/divider-low information, so v7.3.3 will sample LY/STAT/TIMA/TAC/IF rather than adding a timing-sensitive background thread.
