#!/usr/bin/env python3
from pathlib import Path

H = Path('reader_core/src/crystal/hook.rs')
T = Path('reader_core/src/crystal/trace.rs')


def need(text: str, marker: str, label: str) -> None:
    if marker not in text:
        raise SystemExit(f'v715 missing {label}: {marker}')


def rep(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'v715 {label}: expected 1 match, got {n}')
    return text.replace(old, new, 1)


h = H.read_text()
t = T.read_text()

# v7.1.5 is a measurement-only extension to v7.1.4.  It MUST preserve the
# Endpoint v4.4 PURETAIL rule: no DIV/state/tick/emulator-memory reads at the
# final Random PCs.  We only copy a few ARM registers that are already supplied
# to gb_read_mem by the hook trampoline.
for marker, label in [
    ('static mut ENDPOINT_FAST_TAIL: bool = false;', 'PURETAIL flag'),
    ('static mut ENDPOINT_FAST_CALLS: u8 = 0;', 'PURETAIL route counter'),
    ('if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68)', 'PURETAIL fast return'),
]:
    need(h, marker, label)
for marker, label in [
    ('S714 SCAN', 'v714 scan UI'),
    ('S714 READY UP+B', 'v714 READY UI'),
    ('fn rebind_known_post_v713', 'CrossBranch resolver'),
    ('fn enter_stage3_learn', 'generic LEARN'),
    ('practical_expected716_state', 'rel716 guard'),
    ('practical_expected717_state', 'rel717 guard'),
]:
    need(t, marker, label)

h = rep(
    h,
    '''static mut ENDPOINT_FAST_TAIL: bool = false;\nstatic mut ENDPOINT_FAST_CALLS: u8 = 0;''',
    '''static mut ENDPOINT_FAST_TAIL: bool = false;\nstatic mut ENDPOINT_FAST_CALLS: u8 = 0;\n\n// v7.1.5 PURETAIL fingerprint.  These fields are copied from the ARM register\n// save block already passed to gb_read_mem.  No emulator memory, DIV, RNG\n// state, F604 subtick or host timer is read in the Random fast path.\npub const ENDPOINT_FAST_SIG_MAX: usize = 4;\n#[derive(Clone, Copy)]\npub struct EndpointFastSig {\n    pub r1: u32, pub r2: u32, pub r3: u32, pub r4: u32,\n    pub r5: u32, pub r12: u32, pub lr: u32, pub host_pc: u32,\n}\nimpl EndpointFastSig {\n    const EMPTY: Self = Self { r1:0, r2:0, r3:0, r4:0, r5:0, r12:0, lr:0, host_pc:0 };\n}\nstatic mut ENDPOINT_FAST_SIG: [EndpointFastSig; ENDPOINT_FAST_SIG_MAX] =\n    [EndpointFastSig::EMPTY; ENDPOINT_FAST_SIG_MAX];\nstatic mut ENDPOINT_FAST_SIG_COUNT: u8 = 0;''',
    'fingerprint state insertion',
)

h = rep(
    h,
    '''pub fn endpoint_fast_tail_start() {\n    unsafe {\n        ENDPOINT_FAST_CALLS = 0;\n        ENDPOINT_FAST_TAIL = true;\n    }\n}\n\npub fn endpoint_fast_tail_calls() -> u8 {\n    unsafe { ENDPOINT_FAST_CALLS }\n}\n''',
    '''pub fn endpoint_fast_tail_start() {\n    unsafe {\n        ENDPOINT_FAST_CALLS = 0;\n        ENDPOINT_FAST_SIG_COUNT = 0;\n        ENDPOINT_FAST_TAIL = true;\n    }\n}\n\npub fn endpoint_fast_tail_calls() -> u8 {\n    unsafe { ENDPOINT_FAST_CALLS }\n}\n\npub fn endpoint_fast_tail_sig_count() -> u8 {\n    unsafe { ENDPOINT_FAST_SIG_COUNT }\n}\n\npub fn endpoint_fast_tail_sig(index: usize) -> EndpointFastSig {\n    unsafe {\n        if index < ENDPOINT_FAST_SIG_COUNT.min(ENDPOINT_FAST_SIG_MAX as u8) as usize {\n            ENDPOINT_FAST_SIG[index]\n        } else {\n            EndpointFastSig::EMPTY\n        }\n    }\n}\n''',
    'fingerprint reset/getters',
)

old_fast = '''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {\n        // Count only Random's first rDIV read.  No DIV/state/tick/mcycle reads\n        // are performed in PURETAIL mode; this single host byte increment is\n        // retained solely to distinguish the 3-call and 4-call item branch.\n        if pc == 0x2f60 {\n            unsafe { ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1) };\n        }\n        return;\n    }'''
new_fast = '''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {\n        // Count only Random's first rDIV read.  v7.1.5 also copies a compact\n        // ARM-register fingerprint.  IMPORTANT: do not add reader.div(),\n        // reader.rng_state(), system_tick(), F604 reads, or any GB/emulator\n        // memory access here; those observers were proven to move rDIV.\n        if pc == 0x2f60 {\n            unsafe {\n                let i = ENDPOINT_FAST_CALLS as usize;\n                if i < ENDPOINT_FAST_SIG_MAX {\n                    ENDPOINT_FAST_SIG[i] = EndpointFastSig {\n                        r1: regs[1], r2: regs[2], r3: regs[3], r4: regs[4],\n                        r5: regs[5], r12: regs[12], lr: regs[13], host_pc: regs[14],\n                    };\n                    ENDPOINT_FAST_SIG_COUNT = (i as u8).saturating_add(1);\n                }\n                ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1);\n            }\n        }\n        return;\n    }'''
h = rep(h, old_fast, new_fast, 'PURETAIL compact register capture')

# Append a separate compact CSV section.  It is written only after the result is
# already locked, so filesystem work cannot influence the encounter.
anchor = '''        // v3.5 intentionally omits the heavy differential dump. F604 is now\n        // sampled directly at every rDIV hook, so ordinary probe timing stays clean.\n\n        pnp::trace_file_close();'''
insert = '''        // v3.5 intentionally omits the heavy differential dump. F604 is now\n        // sampled directly at every rDIV hook, so ordinary probe timing stays clean.\n\n        // v7.1.5: compact PURETAIL signature captured without Random-time\n        // emulator-memory reads.  Persist only after DV/result lock.\n        line.clear();\n        let fast_calls = super::hook::endpoint_fast_tail_calls();\n        let fast_sig_count = super::hook::endpoint_fast_tail_sig_count();\n        let _ = write!(line, "\\nfasttail715,version,calls,samples\\nFASTTAIL715,V715,{},{}\\n", fast_calls, fast_sig_count);\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(line, "fasttail715_call,index,r1,r2,r3,r4,r5,r12,lr,host_pc\\n");\n        pnp::trace_file_write(line.as_bytes());\n        let fast_shown = (fast_sig_count as usize).min(super::hook::ENDPOINT_FAST_SIG_MAX);\n        for i in 0..fast_shown {\n            let s = super::hook::endpoint_fast_tail_sig(i);\n            line.clear();\n            let _ = write!(line, "FASTCALL,{},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X}\\n",\n                i, s.r1, s.r2, s.r3, s.r4, s.r5, s.r12, s.lr, s.host_pc);\n            pnp::trace_file_write(line.as_bytes());\n        }\n\n        pnp::trace_file_close();'''
t = rep(t, anchor, insert, 'FASTTAIL715 CSV section')

# UI epoch only; scan criteria and the Stage3 CSV compatibility epoch stay put.
t = t.replace('"S714 ', '"S715 ')

# Static safety assertion on the final Random fast path.  regs[] loads and
# static assignments are allowed; timing/emulator reads are not.
start = h.find('if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68)')
end = h.find('        return;\n    }', start)
if start < 0 or end < 0:
    raise SystemExit('v715 cannot locate final PURETAIL block')
block = h[start:end]
for forbidden in ['reader.div(', 'rng_state(', 'system_tick(', 'pnp::read', 'read_volatile', 'gb_mem', 'mcycle =']:
    if forbidden in block:
        raise SystemExit(f'v715 forbidden Random-time observer in PURETAIL block: {forbidden}')

for marker in ['EndpointFastSig', 'ENDPOINT_FAST_SIG_MAX', 'endpoint_fast_tail_sig_count', 'FASTTAIL715,V715']:
    need(h if marker != 'FASTTAIL715,V715' else t, marker, marker)
for marker in ['S715 SCAN', 'S715 READY UP+B', 'S715 LEARN P', 'fn rebind_known_post_v713', 'fn enter_stage3_learn', 'practical_expected716_state', 'practical_expected717_state']:
    need(t, marker, marker)
if 'S714 SCAN' in t:
    raise SystemExit('v715 stale S714 SCAN remains')

H.write_text(h)
T.write_text(t)
print('Applied Suicune v7.1.5 PureTailFingerprint: register-only final Random signature; no timing/emulator reads added')
