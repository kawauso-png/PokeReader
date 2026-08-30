#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
s = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    s = s.replace(old, new, 1)


# v4.2 calibration build: once DV-2 has been captured, stop only the heavy
# Deep snapshot stream.  CALL_LOG deliberately remains active so the final
# 2F60/2F68 sequence can be measured without the 64+128+128 byte snapshots
# running on every 2F60 hook.
replace_once(
    """            if !self.endpoint_pause_requested {
                self.endpoint_pause_requested = true;
                pnp::request_pause();
            }""",
    """            if !self.endpoint_pause_requested {
                self.endpoint_pause_requested = true;
                // Endpoint v4.2 LIGHTTAIL: keep the lightweight per-rDIV
                // CALL_LOG running, but remove Deep snapshot overhead from the
                // final two advances and the 3/4-call DV burst.
                deep_log_stop();
                pnp::request_pause();
            }""",
    "stop deep logging at endpoint",
)

# Distinguish the calibration build on screen while preserving the existing
# ENDPOINT CSV row format for offline parsers.
replace_once(
    '                "EP +{} S{:04X}",',
    '                "EP42 +{} S{:04X}",',
    "endpoint screen marker",
)

path.write_text(s)
print("Applied Suicune Endpoint Probe v4.2 LIGHTTAIL")
