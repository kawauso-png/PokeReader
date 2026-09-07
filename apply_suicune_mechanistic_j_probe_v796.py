#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# Materialize the compact precomputed table beside trace.rs. The repository stores
# a zlib+base64 stream split into fifteen small text chunks.
import base64, zlib
parts = [Path(f'suicune_j_table_v796_b64_part{i}.txt').read_text().strip() for i in range(15)]
table_bin = zlib.decompress(base64.b64decode(''.join(parts)))
expected = 15957 * 8
if len(table_bin) != expected:
    raise SystemExit(f'v796 table size: expected {expected}, got {len(table_bin)}')
Path('reader_core/src/crystal/suicune_j_table_v796.bin').write_bytes(table_bin)

def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v796 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.9.6: deterministic PRE-UP J predictor.
# The runtime table is derived offline from the user's JP Crystal ROM; no ROM
# bytes are embedded. Each 8-byte entry is <u32 FNV key, u16 cycles27,
# u16 cycles28>, sorted by key. The normalized key uses Ch1-Ch3 only and ignores
# four phase-only fields per 0x32-byte channel: +05, +08, +09, +20.
needle = '''static mut V792_AUDIO_PRE_TARGET: u32 = 0xffffffff;\n'''
insert = '''static mut V792_AUDIO_PRE_TARGET: u32 = 0xffffffff;\n\nconst V796_J_TABLE_COUNT: usize = 15957;\nconst V796_J_TABLE_BYTES: usize = V796_J_TABLE_COUNT * 8;\nconst V796_J_TABLE: &[u8; V796_J_TABLE_BYTES] =\n    include_bytes!("suicune_j_table_v796.bin");\nconst V796_FNV_OFFSET: u32 = 0x811c9dc5;\nconst V796_FNV_PRIME: u32 = 0x01000193;\nconst V796_K10: i32 = 71019; // K=7101.9 M-cycle, stored in tenths\nconst V796_RESID10: i32 = 141; // development max |residual| = 14.1 M\nstatic mut V796_JPRED_VALID: bool = false;\nstatic mut V796_JPRED_KEY: u32 = 0;\nstatic mut V796_JPRED_C27: u16 = 0;\nstatic mut V796_JPRED_C28: u16 = 0;\nstatic mut V796_JPRED_J27_10: i32 = 0;\nstatic mut V796_JPRED_J28_10: i32 = 0;\nstatic mut V796_JPRED_MIN10: i32 = 0;\nstatic mut V796_JPRED_MAX10: i32 = 0;\n\nfn v796_audio_key(audio: &[u8; V792_AUDIO_PRE_LEN]) -> u32 {\n    let mut h = V796_FNV_OFFSET;\n    // AUDIOPRE[0] is wMusicPlaying. Ch1 begins at +1. Hash Ch1-Ch3.\n    for j in 0..(3 * 0x32) {\n        let off = j % 0x32;\n        if off == 0x05 || off == 0x08 || off == 0x09 || off == 0x20 {\n            continue;\n        }\n        h ^= audio[1 + j] as u32;\n        h = h.wrapping_mul(V796_FNV_PRIME);\n    }\n    h\n}\n\nfn v796_table_u16(base: usize) -> u16 {\n    (V796_J_TABLE[base] as u16) | ((V796_J_TABLE[base + 1] as u16) << 8)\n}\n\nfn v796_table_u32(base: usize) -> u32 {\n    (V796_J_TABLE[base] as u32)\n        | ((V796_J_TABLE[base + 1] as u32) << 8)\n        | ((V796_J_TABLE[base + 2] as u32) << 16)\n        | ((V796_J_TABLE[base + 3] as u32) << 24)\n}\n\nfn v796_lookup_cycles(key: u32) -> Option<(u16, u16)> {\n    let mut lo = 0usize;\n    let mut hi = V796_J_TABLE_COUNT;\n    while lo < hi {\n        let mid = lo + (hi - lo) / 2;\n        let base = mid * 8;\n        let mk = v796_table_u32(base);\n        if mk < key {\n            lo = mid + 1;\n        } else {\n            hi = mid;\n        }\n    }\n    if lo >= V796_J_TABLE_COUNT {\n        return None;\n    }\n    let base = lo * 8;\n    if v796_table_u32(base) != key {\n        return None;\n    }\n    Some((v796_table_u16(base + 4), v796_table_u16(base + 6)))\n}\n\nunsafe fn v796_predict_j_from_audiopre() {\n    V796_JPRED_VALID = false;\n    if !V792_AUDIO_PRE_VALID {\n        return;\n    }\n    let key = v796_audio_key(&V792_AUDIO_PRE);\n    V796_JPRED_KEY = key;\n    if let Some((c27, c28)) = v796_lookup_cycles(key) {\n        let j27 = (c27 as i32) * 10 - V796_K10;\n        let j28 = (c28 as i32) * 10 - V796_K10;\n        V796_JPRED_C27 = c27;\n        V796_JPRED_C28 = c28;\n        V796_JPRED_J27_10 = j27;\n        V796_JPRED_J28_10 = j28;\n        let center_min = if j27 < j28 { j27 } else { j28 };\n        let center_max = if j27 > j28 { j27 } else { j28 };\n        V796_JPRED_MIN10 = center_min - V796_RESID10;\n        V796_JPRED_MAX10 = center_max + V796_RESID10;\n        V796_JPRED_VALID = true;\n    }\n}\n'''
t = rep(t, needle, insert, 'globals/table')

needle2 = '''            V792_AUDIO_PRE_TARGET = rng_advance();\n            V792_AUDIO_PRE_VALID = true;\n        }\n\n        self.probe_target = ProbeTarget {\n'''
insert2 = '''            V792_AUDIO_PRE_TARGET = rng_advance();\n            V792_AUDIO_PRE_VALID = true;\n            // Pure host-side lookup while the guest remains frozen.\n            v796_predict_j_from_audiopre();\n        }\n\n        self.probe_target = ProbeTarget {\n'''
t = rep(t, needle2, insert2, 'arm predictor')

needle3 = '''        line.clear();\n        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");\n'''
insert3 = '''        line.clear();\n        let _ = write!(line, "\\njpred,version,valid,target,key,cycles27,cycles28,j27_x10,j28_x10,jmin_x10,jmax_x10\\n");\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        unsafe {\n            let _ = write!(line, "JPRED,V796,{},{},{:08X},{},{},{},{},{},{}\\n",\n                V796_JPRED_VALID as u8, V792_AUDIO_PRE_TARGET, V796_JPRED_KEY,\n                V796_JPRED_C27, V796_JPRED_C28, V796_JPRED_J27_10,\n                V796_JPRED_J28_10, V796_JPRED_MIN10, V796_JPRED_MAX10);\n        }\n        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");\n'''
t = rep(t, needle3, insert3, 'save JPRED')

needle4 = 'STALLPHASE,V792,rel0-40+vblankirq+cpuctx84+audiopre'
if t.count(needle4) != 1:
    raise SystemExit(f'v796 marker: expected 1 match, got {t.count(needle4)}')
t = t.replace(needle4, 'STALLPHASE,V796,rel0-40+vblankirq+cpuctx84+audiopre+jpred', 1)

T.write_text(t)
print('Applied v7.9.6 mechanistic J predictor: AUDIOPRE -> FNV32 -> 15957 table -> cycles27/28 -> J envelope')
