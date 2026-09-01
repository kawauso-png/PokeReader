#!/usr/bin/env python3
from pathlib import Path
import base64
import zlib

# v6.4 payload transport wrapper.
# The two payload files are ordinary Git blobs; Git already verifies their
# contents.  Avoid a second hand-maintained checksum layer, which caused the
# previous CI failures when wrapper/payload commits raced each other.
PARTS = [
    Path("apply_suicune_practical_shiny_v64_payload_0.txt"),
    Path("apply_suicune_practical_shiny_v64_payload_1.txt"),
]
EXPECTED_LENGTHS = [6000, 4717]

chunks = []
for path, expected_len in zip(PARTS, EXPECTED_LENGTHS):
    text = path.read_text().strip()
    if len(text) != expected_len:
        raise SystemExit(f"v6.4 payload size mismatch: {path} got {len(text)}, expected {expected_len}")
    chunks.append(text)

payload = "".join(chunks).encode("ascii")
try:
    decoded = zlib.decompress(base64.b85decode(payload)).decode("utf-8")
except Exception as exc:
    raise SystemExit(f"v6.4 payload decode failed: {exc}")

# Generator bug found by CI run 33451620629: lane prototypes are bytes
# (b'A'/b'B'), so chr(proto) raises TypeError on Python 3.13.  Patch exactly
# the known generator expression before execution.
old = "chr(proto)"
new = "proto.decode()"
count = decoded.count(old)
if count != 1:
    raise SystemExit(f"v6.4 generator fix anchor mismatch: {count}")
decoded = decoded.replace(old, new, 1)

# Semantic transport validation.  If either payload is stale/truncated but
# happens to decode, do not touch the source tree.
required = [
    "Practical Shiny",
    "S64",
    "W4",
    "PATH MISS",
]
missing = [marker for marker in required if marker not in decoded]
if missing:
    raise SystemExit(f"v6.4 decoded payload missing markers: {missing}")

exec(compile(decoded, "apply_suicune_practical_shiny_v64.decoded.py", "exec"))
