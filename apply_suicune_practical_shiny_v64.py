#!/usr/bin/env python3
from pathlib import Path
import base64
import hashlib
import zlib

PARTS = [
    Path("apply_suicune_practical_shiny_v64_payload_0.txt"),
    Path("apply_suicune_practical_shiny_v64_payload_1.txt"),
]
EXPECTED_PAYLOAD_SHA256 = "d068c8bdf81aed79b152796e07ce241d5ea0c4aad4d39b36bfa703b6226a593b"
EXPECTED_SCRIPT_SHA256 = "9ed5d557a900c34736d4717f63be9d8b2c02052d54bd8ca4650e940abd1f2f9d"

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
