#!/usr/bin/env python3
from pathlib import Path
import base64
import hashlib
import zlib

PARTS = [
    Path("apply_suicune_practical_shiny_v64_payload_0.txt"),
    Path("apply_suicune_practical_shiny_v64_payload_1.txt"),
]
EXPECTED_PAYLOAD_SHA256 = "b9958a780b7c5d75d3c1bd45597e0e5fd7d2c6ba7bdaced5ff64d83c830949d2"
EXPECTED_SCRIPT_SHA256 = "455d5d4e516612051311afcfe59c34c2a3a63ccb1a78faa460078c4b2d7e1744"

payload = "".join(p.read_text().strip() for p in PARTS).encode("ascii")
if hashlib.sha256(payload).hexdigest() != EXPECTED_PAYLOAD_SHA256:
    raise SystemExit("v6.4 payload checksum mismatch")

try:
    script = zlib.decompress(base64.b85decode(payload))
except Exception as exc:
    raise SystemExit(f"v6.4 payload decode failed: {exc}")

if hashlib.sha256(script).hexdigest() != EXPECTED_SCRIPT_SHA256:
    raise SystemExit("v6.4 decoded script checksum mismatch")

exec(compile(script, "apply_suicune_practical_shiny_v64.decoded.py", "exec"))
