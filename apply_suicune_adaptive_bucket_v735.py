#!/usr/bin/env python3
from pathlib import Path
import base64, zlib

parts = [
    Path('apply_suicune_adaptive_bucket_v735_payload_0.txt'),
    Path('apply_suicune_adaptive_bucket_v735_payload_1.txt'),
    Path('apply_suicune_adaptive_bucket_v735_payload_2.txt'),
    Path('apply_suicune_adaptive_bucket_v735_payload_3.txt'),
]
RUST_B85 = ''.join(p.read_text().strip() for p in parts)
code_b85 = Path('apply_suicune_adaptive_bucket_v735_code.txt').read_text().strip()
try:
    code = zlib.decompress(base64.b85decode(code_b85)).decode('utf-8')
except Exception as exc:
    raise SystemExit(f'v735 code payload decode failed: {exc}')
exec(compile(code, 'apply_suicune_adaptive_bucket_v735.decoded.py', 'exec'), globals())
