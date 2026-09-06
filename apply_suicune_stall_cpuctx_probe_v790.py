#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v790 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.9.0: observation-only single snapshot at the decisive rel27 DIV=0x84
# present.  0197/0198 had identical PC/bank/DIV/F604 there but diverged in the
# immediately following present.  Capture the existing 64-byte emulator CPU
# context once, rather than guessing guest WRAM addresses. No game state write.

t = rep(t,
'''static mut TRACE_ENTRIES: [TraceEntry; MAX_FRAMES] = [TraceEntry::EMPTY; MAX_FRAMES];\n''',
'''static mut TRACE_ENTRIES: [TraceEntry; MAX_FRAMES] = [TraceEntry::EMPTY; MAX_FRAMES];\n\nconst V790_CPU_CTX_BASE: u32 = 0x0022f5e0;\nconst V790_CPU_CTX_LEN: usize = 64;\nstatic mut V790_CPU_CTX: [u8; V790_CPU_CTX_LEN] = [0; V790_CPU_CTX_LEN];\nstatic mut V790_CPU_CTX_VALID: bool = false;\nstatic mut V790_CPU_CTX_PC: u16 = 0xffff;\nstatic mut V790_CPU_CTX_DIV: u8 = 0xff;\nstatic mut V790_CPU_CTX_SUB: u8 = 0xff;\nstatic mut V790_CPU_CTX_BANK: u8 = 0xff;\n''',
'globals')

t = rep(t,
'''        deep_log_clear();\n        self.probe_target = ProbeTarget {''',
'''        deep_log_clear();\n        unsafe {\n            V790_CPU_CTX_VALID = false;\n            V790_CPU_CTX_PC = 0xffff;\n            V790_CPU_CTX_DIV = 0xff;\n            V790_CPU_CTX_SUB = 0xff;\n            V790_CPU_CTX_BANK = 0xff;\n        }\n        self.probe_target = ProbeTarget {''',
'arm reset')

anchor = '''        self.entries[self.len] = TraceEntry {\n'''
insert = '''        // v7.9.0 decisive pre-split CPU context.  The guest is stopped while\n        // this tiny 64-byte host copy runs. Capture exactly once at rel27/live DIV 84.\n        if self.probe_session && sample_rel == 27 && sample_live_div == 0x84 {\n            unsafe {\n                if !V790_CPU_CTX_VALID {\n                    let dst = core::ptr::addr_of_mut!(V790_CPU_CTX).cast::<u8>();\n                    pnp::read_into_raw(V790_CPU_CTX_BASE, dst, V790_CPU_CTX_LEN);\n                    V790_CPU_CTX_PC = sample_pc;\n                    V790_CPU_CTX_DIV = sample_live_div;\n                    V790_CPU_CTX_SUB = sample_live_sub;\n                    V790_CPU_CTX_BANK = sample_rom_bank;\n                    V790_CPU_CTX_VALID = true;\n                }\n            }\n        }\n\n'''
if t.count(anchor) != 1:
    raise SystemExit(f'v790 record anchor: expected 1 match, got {t.count(anchor)}')
t = t.replace(anchor, insert + anchor, 1)

needle = '''        // Second section: every Random call, which is what shows how the DVs\n'''
marker = '''        line.clear();\n        let _ = write!(line, "\\nstall_cpu_ctx,version,valid,pc,div,sub,bank,base,len,ctx_hex\\n");\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        unsafe {\n            let _ = write!(line, "STALLCTX,V790,{},{:04X},{:02X},{:02X},{:02X},{:08X},{} ,",\n                V790_CPU_CTX_VALID as u8, V790_CPU_CTX_PC, V790_CPU_CTX_DIV,\n                V790_CPU_CTX_SUB, V790_CPU_CTX_BANK, V790_CPU_CTX_BASE, V790_CPU_CTX_LEN);\n            if V790_CPU_CTX_VALID {\n                for b in V790_CPU_CTX.iter() {\n                    let _ = write!(line, "{:02X}", *b);\n                }\n            }\n            let _ = write!(line, "\\n");\n        }\n        pnp::trace_file_write(line.as_bytes());\n\n'''
if t.count(needle) != 1:
    raise SystemExit(f'v790 save anchor: expected 1 match, got {t.count(needle)}')
t = t.replace(needle, marker + needle, 1)

needle2 = 'STALLPHASE,V789,rel0-40+vblankirq'
if needle2 not in t:
    raise SystemExit('v790 V789 lineage marker missing')
t = t.replace(needle2, 'STALLPHASE,V790,rel0-40+vblankirq+cpuctx84', 1)

T.write_text(t)
print('Applied v7.9.0 Stall CPU Context Probe: one read-only 64B snapshot at rel27 DIV84')
