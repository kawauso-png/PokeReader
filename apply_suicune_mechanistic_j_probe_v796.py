#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
B = Path('reader_core/src/pnp/bindings.rs')
U = Path('reader_core/src/pnp/utils.rs')
C = Path('3gx/sources/main.c')
t = T.read_text()
b = B.read_text()
u = U.read_text()
c = C.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v796 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.9.6: deterministic PRE-UP J predictor.
# The 15957-entry table is derived offline from the user's JP Crystal ROM, but
# the ROM is never embedded. To keep the 3GX build independent of that binary,
# the derived 127656-byte table is loaded read-only from SDMC once, while the
# guest is already frozen at the physical-UP Target.
#
# SD path:
#   /luma/plugins/pokereader/suicune_j_table_v796.bin
#
# Entry format: <u32 FNV key, u16 cycles27, u16 cycles28>, strictly sorted by
# key. The key hashes Ch1-Ch3 and ignores four phase-only fields per channel.
needle = '''static mut V792_AUDIO_PRE_TARGET: u32 = 0xffffffff;\n'''
insert = '''static mut V792_AUDIO_PRE_TARGET: u32 = 0xffffffff;\n\nconst V796_J_TABLE_COUNT: usize = 15957;\nconst V796_J_TABLE_BYTES: usize = V796_J_TABLE_COUNT * 8;\nstatic mut V796_J_TABLE: [u8; V796_J_TABLE_BYTES] = [0; V796_J_TABLE_BYTES];\nstatic mut V796_J_TABLE_READY: bool = false;\nstatic mut V796_J_TABLE_LOAD_LEN: u32 = 0;\nconst V796_FNV_OFFSET: u32 = 0x811c9dc5;\nconst V796_FNV_PRIME: u32 = 0x01000193;\nconst V796_K10: i32 = 71019; // K=7101.9 M-cycle, stored in tenths\nconst V796_RESID10: i32 = 141; // development max |residual| = 14.1 M\nstatic mut V796_JPRED_VALID: bool = false;\nstatic mut V796_JPRED_KEY: u32 = 0;\nstatic mut V796_JPRED_C27: u16 = 0;\nstatic mut V796_JPRED_C28: u16 = 0;\nstatic mut V796_JPRED_J27_10: i32 = 0;\nstatic mut V796_JPRED_J28_10: i32 = 0;\nstatic mut V796_JPRED_MIN10: i32 = 0;\nstatic mut V796_JPRED_MAX10: i32 = 0;\n\nfn v796_audio_key(audio: &[u8; V792_AUDIO_PRE_LEN]) -> u32 {\n    let mut h = V796_FNV_OFFSET;\n    // AUDIOPRE[0] is wMusicPlaying. Ch1 begins at +1. Hash Ch1-Ch3.\n    for j in 0..(3 * 0x32) {\n        let off = j % 0x32;\n        if off == 0x05 || off == 0x08 || off == 0x09 || off == 0x20 {\n            continue;\n        }\n        h ^= audio[1 + j] as u32;\n        h = h.wrapping_mul(V796_FNV_PRIME);\n    }\n    h\n}\n\nunsafe fn v796_ensure_table() -> bool {\n    if V796_J_TABLE_READY {\n        return true;\n    }\n    let dst = core::ptr::addr_of_mut!(V796_J_TABLE).cast::<u8>();\n    let got = pnp::v796_table_load(dst, V796_J_TABLE_BYTES as u32);\n    V796_J_TABLE_LOAD_LEN = got;\n    V796_J_TABLE_READY = got == V796_J_TABLE_BYTES as u32;\n    V796_J_TABLE_READY\n}\n\nunsafe fn v796_table_u16(base: usize) -> u16 {\n    (V796_J_TABLE[base] as u16) | ((V796_J_TABLE[base + 1] as u16) << 8)\n}\n\nunsafe fn v796_table_u32(base: usize) -> u32 {\n    (V796_J_TABLE[base] as u32)\n        | ((V796_J_TABLE[base + 1] as u32) << 8)\n        | ((V796_J_TABLE[base + 2] as u32) << 16)\n        | ((V796_J_TABLE[base + 3] as u32) << 24)\n}\n\nunsafe fn v796_lookup_cycles(key: u32) -> Option<(u16, u16)> {\n    let mut lo = 0usize;\n    let mut hi = V796_J_TABLE_COUNT;\n    while lo < hi {\n        let mid = lo + (hi - lo) / 2;\n        let base = mid * 8;\n        let mk = v796_table_u32(base);\n        if mk < key {\n            lo = mid + 1;\n        } else {\n            hi = mid;\n        }\n    }\n    if lo >= V796_J_TABLE_COUNT {\n        return None;\n    }\n    let base = lo * 8;\n    if v796_table_u32(base) != key {\n        return None;\n    }\n    Some((v796_table_u16(base + 4), v796_table_u16(base + 6)))\n}\n\nunsafe fn v796_predict_j_from_audiopre() {\n    V796_JPRED_VALID = false;\n    if !V792_AUDIO_PRE_VALID || !v796_ensure_table() {\n        return;\n    }\n    let audio = &*core::ptr::addr_of!(V792_AUDIO_PRE);\n    let key = v796_audio_key(audio);\n    V796_JPRED_KEY = key;\n    if let Some((c27, c28)) = v796_lookup_cycles(key) {\n        let j27 = (c27 as i32) * 10 - V796_K10;\n        let j28 = (c28 as i32) * 10 - V796_K10;\n        V796_JPRED_C27 = c27;\n        V796_JPRED_C28 = c28;\n        V796_JPRED_J27_10 = j27;\n        V796_JPRED_J28_10 = j28;\n        let center_min = if j27 < j28 { j27 } else { j28 };\n        let center_max = if j27 > j28 { j27 } else { j28 };\n        V796_JPRED_MIN10 = center_min - V796_RESID10;\n        V796_JPRED_MAX10 = center_max + V796_RESID10;\n        V796_JPRED_VALID = true;\n    }\n}\n'''
t = rep(t, needle, insert, 'trace globals/table')

needle2 = '''            V792_AUDIO_PRE_TARGET = rng_advance();\n            V792_AUDIO_PRE_VALID = true;\n        }\n\n        self.probe_target = ProbeTarget {\n'''
insert2 = '''            V792_AUDIO_PRE_TARGET = rng_advance();\n            V792_AUDIO_PRE_VALID = true;\n            // Host-side SD load/lookup only; the guest remains frozen.\n            v796_predict_j_from_audiopre();\n        }\n\n        self.probe_target = ProbeTarget {\n'''
t = rep(t, needle2, insert2, 'arm predictor')

needle3 = '''        line.clear();\n        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");\n'''
insert3 = '''        line.clear();\n        let _ = write!(line, "\\njpred,version,valid,target,table_ready,table_len,key,cycles27,cycles28,j27_x10,j28_x10,jmin_x10,jmax_x10\\n");\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        unsafe {\n            let _ = write!(line, "JPRED,V796,{},{},{},{},{:08X},{},{},{},{},{},{}\\n",\n                V796_JPRED_VALID as u8, V792_AUDIO_PRE_TARGET,\n                V796_J_TABLE_READY as u8, V796_J_TABLE_LOAD_LEN, V796_JPRED_KEY,\n                V796_JPRED_C27, V796_JPRED_C28, V796_JPRED_J27_10,\n                V796_JPRED_J28_10, V796_JPRED_MIN10, V796_JPRED_MAX10);\n        }\n        pnp::trace_file_write(line.as_bytes());\n\n        line.clear();\n        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");\n'''
t = rep(t, needle3, insert3, 'save JPRED')

needle4 = 'STALLPHASE,V792,rel0-40+vblankirq+cpuctx84+audiopre'
if t.count(needle4) != 1:
    raise SystemExit(f'v796 marker: expected 1 match, got {t.count(needle4)}')
t = t.replace(needle4, 'STALLPHASE,V796,rel0-40+vblankirq+cpuctx84+audiopre+jpred-sd', 1)

# Show the prediction before physical UP. A missing/bad table is explicitly
# fail-closed in the overlay so the user does not spend a physical attempt.
ui_old = '''        } else if self.probe_session && self.probe_active && !self.practical_active {\n            pnp::println!("S732 CONTROL RUN");\n        } else if self.practical_miss != 0 {\n'''
ui_new = '''        } else if self.probe_session && self.probe_active && !self.practical_active {\n            unsafe {\n                if V796_JPRED_VALID {\n                    pnp::println!("S796 JPRED READY");\n                    pnp::println!("C27 {} C28 {}", V796_JPRED_C27, V796_JPRED_C28);\n                    pnp::println!("Jx10 {} / {}", V796_JPRED_J27_10, V796_JPRED_J28_10);\n                    pnp::println!("WINx10 {}..{}", V796_JPRED_MIN10, V796_JPRED_MAX10);\n                    pnp::println!("PRESS UP BLIND");\n                } else if !V796_J_TABLE_READY {\n                    pnp::println!("S796 TABLE LOAD ERR");\n                    pnp::println!("GOT {} NEED {}", V796_J_TABLE_LOAD_LEN, V796_J_TABLE_BYTES);\n                    pnp::println!("DO NOT PRESS UP");\n                } else {\n                    pnp::println!("S796 TABLE KEY MISS");\n                    pnp::println!("KEY {:08X}", V796_JPRED_KEY);\n                    pnp::println!("DO NOT PRESS UP");\n                }\n            }\n        } else if self.practical_miss != 0 {\n'''
t = rep(t, ui_old, ui_new, 'pre-UP JPRED UI')

# Rust FFI declaration and test stub.
b = rep(
    b,
    '''    pub fn host_trace_written_slot() -> u32;\n    pub fn get_remaster_version() -> u16;\n''',
    '''    pub fn host_trace_written_slot() -> u32;\n    pub fn host_v796_table_load(dst: *mut u8, len: u32) -> u32;\n    pub fn get_remaster_version() -> u16;\n''',
    'binding decl',
)
b = rep(
    b,
    '''    pub extern "C" fn host_trace_written_slot() -> u32 {\n        0\n    }\n    #[no_mangle]\n    pub extern "C" fn osGetTime() -> u64 {\n''',
    '''    pub extern "C" fn host_trace_written_slot() -> u32 {\n        0\n    }\n    #[no_mangle]\n    pub extern "C" fn host_v796_table_load(_dst: *mut u8, _len: u32) -> u32 {\n        0\n    }\n    #[no_mangle]\n    pub extern "C" fn osGetTime() -> u64 {\n''',
    'binding stub',
)

# Small public wrapper used by the Crystal trace module.
if 'pub unsafe fn v796_table_load' in u:
    raise SystemExit('v796 utils wrapper already present')
u += '''\n/// v7.9.6: load the derived Suicune J table from SDMC into plugin memory.\n/// Read-only with respect to the guest/VC process.\npub unsafe fn v796_table_load(dst: *mut u8, len: u32) -> u32 {\n    bindings::host_v796_table_load(dst, len)\n}\n'''

# C-side SDMC loader. Uses the same FSUSER path already used by trace output,
# but opens the table read-only and closes the FS session immediately.
c_anchor = '''u32 host_trace_request(void)\n{\n'''
c_insert = '''u32 host_v796_table_load(void *dst, u32 len)\n{\n    FS_Archive sdmc;\n    Handle file = 0;\n    u64 size = 0;\n    u32 bytes_read = 0;\n    Result res;\n\n    if (dst == NULL || len == 0)\n        return 0;\n\n    res = fsInit();\n    if (R_FAILED(res))\n        return 0;\n\n    res = FSUSER_OpenArchive(&sdmc, ARCHIVE_SDMC, fsMakePath(PATH_EMPTY, ""));\n    if (R_FAILED(res))\n    {\n        fsExit();\n        return 0;\n    }\n\n    res = FSUSER_OpenFile(&file, sdmc,\n        fsMakePath(PATH_ASCII, "/luma/plugins/pokereader/suicune_j_table_v796.bin"),\n        FS_OPEN_READ, 0);\n    if (R_SUCCEEDED(res))\n        res = FSFILE_GetSize(file, &size);\n    if (R_SUCCEEDED(res) && size == (u64)len)\n        res = FSFILE_Read(file, &bytes_read, 0, dst, len);\n\n    if (file != 0)\n        FSFILE_Close(file);\n    FSUSER_CloseArchive(sdmc);\n    fsExit();\n\n    if (R_FAILED(res) || size != (u64)len || bytes_read != len)\n        return 0;\n    return bytes_read;\n}\n\n'''
if c.count(c_anchor) != 1:
    raise SystemExit(f'v796 C loader anchor: expected 1 match, got {c.count(c_anchor)}')
c = c.replace(c_anchor, c_insert + c_anchor, 1)

T.write_text(t)
B.write_text(b)
U.write_text(u)
C.write_text(c)
print('Applied v7.9.6 mechanistic J predictor: AUDIOPRE -> SD table -> cycles27/28 -> J envelope + pre-UP UI')
