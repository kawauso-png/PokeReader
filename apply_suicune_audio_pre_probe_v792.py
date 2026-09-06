#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v792 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.9.2: capture the whole Crystal audio WRAM block while the game is already
# paused at the exact physical-UP Target. This is observation-only and happens
# before resume, so it cannot perturb the decisive LCD-off transport.
# International Crystal symbols place Audio RAM at C100-C2BF (448 bytes). Keep
# the raw block so the Japanese layout can be validated empirically.

t = rep(t,
'''const V790_CPU_CTX_BASE: u32 = 0x0022f5e0;\n''',
'''const V792_AUDIO_PRE_BASE: u32 = 0x0000c100;\nconst V792_AUDIO_PRE_LEN: usize = 0x1c0; // C100..C2BF inclusive\nstatic mut V792_AUDIO_PRE: [u8; V792_AUDIO_PRE_LEN] = [0; V792_AUDIO_PRE_LEN];\nstatic mut V792_AUDIO_PRE_VALID: bool = false;\nstatic mut V792_AUDIO_PRE_TARGET: u32 = 0xffffffff;\n\nconst V790_CPU_CTX_BASE: u32 = 0x0022f5e0;\n''',
'globals')

# The generated v7.9.1 arm function contains many earlier diagnostic resets.
# Anchor immediately after the final pre-VBlank capture stop and before the
# ProbeTarget snapshot; this is stable in the actual packaged v7.9.1 source.
needle = '''        pre_vblank_timing_capture_stop();\n        self.probe_target = ProbeTarget {\n'''
insert = '''        pre_vblank_timing_capture_stop();\n\n        // v7.9.2 PRE-UP audio snapshot. This function is called from the host\n        // freeze loop while the guest is paused, so the 448 read-only WRAM\n        // reads occur before Exact2/M14 resume and cannot consume guest cycles.\n        unsafe {\n            for i in 0..V792_AUDIO_PRE_LEN {\n                V792_AUDIO_PRE[i] = gb_mem::read_u8(V792_AUDIO_PRE_BASE + i as u32);\n            }\n            V792_AUDIO_PRE_TARGET = rng_advance();\n            V792_AUDIO_PRE_VALID = true;\n        }\n\n        self.probe_target = ProbeTarget {\n'''
t = rep(t, needle, insert, 'arm snapshot')

needle2 = '''        line.clear();\n        let _ = write!(line, "\\nstall_cpu_ctx,version,valid,target,pc,div,sub,bank,base,len,ctx_hex\\n");\n'''
marker = '''        line.clear();\n        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        unsafe {\n            let _ = write!(line, "AUDIOPRE,V792,{},{},{:04X},{},",\n                V792_AUDIO_PRE_VALID as u8, V792_AUDIO_PRE_TARGET,\n                V792_AUDIO_PRE_BASE as u16, V792_AUDIO_PRE_LEN);\n            if V792_AUDIO_PRE_VALID {\n                for i in 0..V792_AUDIO_PRE_LEN {\n                    let _ = write!(line, "{:02X}", V792_AUDIO_PRE[i]);\n                }\n            }\n            let _ = write!(line, "\\n");\n        }\n        pnp::trace_file_write(line.as_bytes());\n\n'''
if t.count(needle2) != 1:
    raise SystemExit(f'v792 save anchor: expected 1 match, got {t.count(needle2)}')
t = t.replace(needle2, marker + needle2, 1)

needle3 = 'STALLPHASE,V790,rel0-40+vblankirq+cpuctx84'
if needle3 not in t:
    raise SystemExit('v792 V790 lineage marker missing')
t = t.replace(needle3, 'STALLPHASE,V792,rel0-40+vblankirq+cpuctx84+audiopre', 1)

T.write_text(t)
print('Applied v7.9.2 Audio PRE Probe: read-only C100-C2BF snapshot while paused at Target')
