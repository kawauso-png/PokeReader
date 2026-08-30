# Blue Mewtwo v7.3.3 SAFE IO plan

The remaining historical prediction error is only a few rDIV-high ticks. v7.3.3 will keep the validated v7.2/v7.3.2 execution model (no startup thread, no fast hook, no critical-path I/O) and add ordinary sampled GB IO registers that may expose sub-frame phase:

- FF05 TIMA
- FF07 TAC
- FF0F IF
- FF41 STAT
- FF44 LY

These are read from the same already-mapped flat GB IO memory block as FF04 rDIV during the existing once-per-host-sample trace. The GB-release marker only copies the already-sampled values. CSV writes remain post-battle.
