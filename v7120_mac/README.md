# S7120 Mac frame control

Two separately submitted operations. A neutral step never automatically arms an encounter.

Opcode0 releases 1..65535 neutral frames on the absolute grid start+index*hz/fps (30 or60). A 1..5ms lateness guard aborts a missed slot while paused, with no catch-up release. This allowance is not a prediction-accuracy guarantee. All 56-byte samples (arrival tick, RTC, release tick, ADV, state, PC, cached keys, raw RTC, DIV, elapsed, remaining) are retained in a bounded allocation and saved to mac_samples.bin after the run. Allocation/journal/export/log failure is reported. Report includes sample count, bytes, FNV and first/last samples (all for <=32 frames). Verify hardware results against the prediction before calling them accurate.

Opcode1 binds a shiny DV and future event clock to the exact paused snapshot ID, ADV/seed and four hashes. A fresh export rechecks hashes; then the existing physical-UP Exact2 countdown/M14 path is armed. No button is synthesized and no neutral step is sent. The user holds real UP at the countdown prompt and releases it at the two-poll stop. The armed report records acceptance only; physical launch/outcome must be checked separately in the resulting trace.

128-byte little-endian S7120REQ version2: words4-5 nonce,6-7 stateID,8 ADV,9 seed,10 frames,11 fps,12-13 expiry,14-17 hashes,18 opcode,19-20 neutral start,21 lateness ticks,22 DV,23-24 event launch,25-26 M14 resume. Words27-30 and inactive operation fields are zero. Word31 is FNV1a(first124 bytes). Start/launch <=1hour ahead, expiry <=2hours; launch >10sec ahead and resume 5..6sec after launch. Nonces one-shot; uncertain delivery must be recovered with the same local journal, never blindly resubmitted.

Reload changes the paused input: never reuse an S7119 candidate/delay after reload. Capture S7120, validate short/long neutral steps on hardware, then recompute/verify a candidate for current clock conditions. No RNG/DIV/DV/save restoration or guest RAM writes are added. Physical keys during neutral stepping abort at the next boundary; the affected trial is not neutral. Private ROM/RAM stay local.
