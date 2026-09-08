# PRE candidate pilot: provenance and limits

Baseline: `2fcf028667a29f6890c9d005ce6b1e2ad0b676f9`, workflow run 34098077219, artifact 10009406703. Baseline 3GX SHA256: `256f2c834a7dc129eb3b65b09a2697c47402e67a58693b6e7c347040259aa22e`. The local v7100 generation matched all five C/Rust source files in that artifact byte for byte. `baseline_hashes.json` records those hashes.

The 16 supplied traces were read offline. Neither the ROM nor raw traces are included in this branch. All had neutral=3, advance delta=3, and target phases AP=2A35/SP=2A40. Their neutral steps were A/S=(132,132),(150,150),(168,169).

Eight distinct observed prefix templates across 12 A/r1, D/r1, B/r8 runs provide the 41 ordinary Random updates from target to rel40. Each prefix was replayed against its recorded state40. The tail model uses A fixed A-byte corrections, all 14 S-pulse choices (0..14 pulses), optional D rel42 S and rel577 A exceptions, both observed 677/678 horizons where available, observed stop-to-capture phase templates, and the v781 deep profile cross-products widened to both S anchors. B/r8 has only one horizon/template. Sparse other cells are not modeled. Numeric details are in `model_report.json`.

`paths.json` is the deduplicated union of 3159 counterfactual byte-sum paths. Each tuple is `(sum_A_before_last, sum_S_before_last, last_A, last_S)`; the penultimate and final S outputs are the two DV bytes. Wrapping bytes are accounted for before sums. Carry from cumulative A is retained. This is a derivation artifact, not a library of proven state-independent guest paths.

For every possible target A byte, solve the target S byte that makes final S=AA. Retain it only if the penultimate S is 2A,3A,6A,7A,AA,BA,EA,FA. Pull these target states back through the three neutral steps. `roots.bin` stores LSB-first membership at index `state>>3`, bit `state&7`. 5887/65536 states qualify under these hypotheses. This fraction is not a success probability, an enrichment measurement, or an expected waiting time.

Retrospective coverage: all 11 recorded DVs from the 12 developed-cell runs occur in the union from their real target states. This uses the same data that established the hypotheses; it is not independent validation. There are no shiny examples in the supplied corpus. Changing initial RNG can change guest branches and audio timing. No success-rate or shiny/hour improvement is established, and rejecting unmodeled PRE states may discard actual shiny opportunities.

The host verification exhaustively compares the inversion bitset with forward evaluation for all 65536 roots and checks phase/state/advance mismatch guards. It also pins the unchanged input/Random hook and verifies that the candidate lane cannot enter old rel40 hard-reject logic. DV-2 negatives remain advisory; every correctly armed trial reaches the game's native final DV. These checks establish implementation consistency, not physical-model accuracy.

The plugin adds no Random-call observation hook. The lookup happens at an existing phase check. Frozen-root and arm-time checks are host arithmetic. Candidate/arm/release panels repaint the cached top-screen buffers while paused without calling run_frame or releasing a guest frame. This display change also needs real-device validation. Old calibration files remain diagnostic and are not inputs to this PRE table.

Build: regenerate v799, apply v7100, then apply `apply_suicune_pre_candidate_v7101.py`, run `verify_suicune_v7101.py`, and `make` in the existing devkitarm-rust environment. Do not run the generation chain twice on an already generated working tree.
