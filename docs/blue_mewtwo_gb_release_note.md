Blue Mewtwo: empirical release result

Across traces 0011-0020, the first transition of Game Boy hJoyHeld.A from 1 to 0 occurs exactly 9 sampled frames before DV write in all 10 traces.
Physical 3DS A release appears 8 or 9 frames before DV because host-side HID sampling can lead/lag the Game Boy joypad state by one sample.
Use GB-side A release as the authoritative execution anchor for prediction.
