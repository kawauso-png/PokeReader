# v7.10.18 Mac snapshot transport

After Y+DOWN starts normal search, SELECT stops it. Releasing every key exports
one paused input to `/luma/plugins/pokereader/mac_state.bin`, then publishes
`mac_state.json`. The screen shows MAC SNAPSHOT READY and the real process ID.
The old scan text underneath may remain stale. No automatic resume or launch
is armed; the guest remains paused. Y+DOWN starts another normal search.

The export uses the v7116 payload format, software word 7118, complete hashes
and footer, with a fresh clock reference and a reference schedule 600 seconds
later. This schedule is for offline analysis only. Neither the snapshot nor a
predicted shiny establishes a validated device launch time. The current Mac
receiver cannot send a launch plan or advance the console.

ROM is not exported. The manifest is invalidated before payload replacement,
then written only after complete payload flush/close. Read manifest, payload,
and manifest again; reject changed identity, wrong hashes, truncated transfer,
and any mismatch between header and manifest. Do not upload private RAM/ROM.

This change preserves v7117's search, physical UP, Exactly-2 and M14 behavior.
It does not incorporate the unshipped early-prefix speed experiments.
