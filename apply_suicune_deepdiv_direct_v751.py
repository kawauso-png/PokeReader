#!/usr/bin/env python3
from pathlib import Path

H=Path('reader_core/src/crystal/hook.rs')
T=Path('reader_core/src/crystal/trace.rs')
h=H.read_text(); t=T.read_text()

def need(c,msg):
    if not c: raise SystemExit('v751 '+msg)

# ---------------------------------------------------------------------------
# v7.5.1 diagnostic-only final Random rDIV capture.
# The existing PURETAIL branch returns before the generic telemetry path on
# 2F60/2F68.  Read FF04 exactly once at each final Random rDIV hook and store
# only that byte.  No host tick/F604/state reads are added in the fast path.
# ---------------------------------------------------------------------------
if 'ENDPOINT_FAST_A_DIV_V751' not in h:
    anchor='static mut ENDPOINT_FAST_SIG_COUNT: u8 = 0;\n'
    need(anchor in h,'fast sig count anchor missing')
    block=r'''static mut ENDPOINT_FAST_A_DIV_V751: [u8; ENDPOINT_FAST_SIG_MAX] = [0; ENDPOINT_FAST_SIG_MAX];
static mut ENDPOINT_FAST_S_DIV_V751: [u8; ENDPOINT_FAST_SIG_MAX] = [0; ENDPOINT_FAST_SIG_MAX];
static mut ENDPOINT_FAST_DIV_MASK_V751: [u8; ENDPOINT_FAST_SIG_MAX] = [0; ENDPOINT_FAST_SIG_MAX];

pub fn endpoint_fast_tail_div_v751(index: usize) -> (u8,u8,u8) {
    unsafe {
        if index < ENDPOINT_FAST_SIG_MAX {
            (ENDPOINT_FAST_A_DIV_V751[index], ENDPOINT_FAST_S_DIV_V751[index], ENDPOINT_FAST_DIV_MASK_V751[index])
        } else {
            (0,0,0)
        }
    }
}
'''
    h=h.replace(anchor,anchor+block,1)

# Reset the direct DIV capture whenever the final-tail capture is armed.
if 'ENDPOINT_FAST_A_DIV_V751[i] = 0;' not in h:
    anchor='''        ENDPOINT_FAST_CALLS = 0;\n        ENDPOINT_FAST_SIG_COUNT = 0;\n        ENDPOINT_FAST_TAIL = true;'''
    need(anchor in h,'fast tail start anchor missing')
    repl='''        ENDPOINT_FAST_CALLS = 0;\n        ENDPOINT_FAST_SIG_COUNT = 0;\n        let mut i=0usize;\n        while i<ENDPOINT_FAST_SIG_MAX {\n            ENDPOINT_FAST_A_DIV_V751[i] = 0;\n            ENDPOINT_FAST_S_DIV_V751[i] = 0;\n            ENDPOINT_FAST_DIV_MASK_V751[i] = 0;\n            i+=1;\n        }\n        ENDPOINT_FAST_TAIL = true;'''
    h=h.replace(anchor,repl,1)

# Replace the final Random fast branch.  This is the only place in v751 that
# adds an emulator-memory read to PURETAIL, and it is intentionally limited to
# the 2F60/2F68 FF04 accesses themselves.
if 'ENDPOINT_FAST_DIV_MASK_V751[i] |= 0x01;' not in h:
    old=r'''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        // Count only Random's first rDIV read. v7.1.5 also copies a compact
        // ARM-register fingerprint. Keep this branch register-copy-only: no
        // timing, divider/state, subtick, or emulator-memory observation.
        if pc == 0x2f60 {
            unsafe {
                let i = ENDPOINT_FAST_CALLS as usize;
                if i < ENDPOINT_FAST_SIG_MAX {
                    ENDPOINT_FAST_SIG[i] = EndpointFastSig {
                        r1: regs[1], r2: regs[2], r3: regs[3], r4: regs[4],
                        r5: regs[5], r12: regs[12], lr: regs[13], host_pc: regs[14],
                    };
                    ENDPOINT_FAST_SIG_COUNT = (i as u8).saturating_add(1);
                }
                ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1);
            }
        }
        return;
    }
'''
    need(old in h,'PURETAIL fast branch anchor missing')
    new=r'''    if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68) {
        // v7.5.1 diagnostic: capture the exact FF04 byte at the two Random
        // read PCs. Keep the path minimal: one divider read, no timer/F604 or
        // RNG-state observation.
        let div_now = reader.div();
        if pc == 0x2f60 {
            unsafe {
                let i = ENDPOINT_FAST_CALLS as usize;
                if i < ENDPOINT_FAST_SIG_MAX {
                    ENDPOINT_FAST_A_DIV_V751[i] = div_now;
                    ENDPOINT_FAST_DIV_MASK_V751[i] |= 0x01;
                    ENDPOINT_FAST_SIG[i] = EndpointFastSig {
                        r1: regs[1], r2: regs[2], r3: regs[3], r4: regs[4],
                        r5: regs[5], r12: regs[12], lr: regs[13], host_pc: regs[14],
                    };
                    ENDPOINT_FAST_SIG_COUNT = (i as u8).saturating_add(1);
                }
                ENDPOINT_FAST_CALLS = ENDPOINT_FAST_CALLS.saturating_add(1);
            }
        } else {
            unsafe {
                let i = ENDPOINT_FAST_CALLS.saturating_sub(1) as usize;
                if i < ENDPOINT_FAST_SIG_MAX {
                    ENDPOINT_FAST_S_DIV_V751[i] = div_now;
                    ENDPOINT_FAST_DIV_MASK_V751[i] |= 0x02;
                }
            }
        }
        return;
    }
'''
    h=h.replace(old,new,1)

# Append the direct values immediately after FASTCALL rows.
if 'FASTDIV751' not in t:
    anchor='''        for i in 0..fast_shown {\n            let s = super::hook::endpoint_fast_tail_sig(i);\n            line.clear();\n            let _ = write!(line, "FASTCALL,{},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X},{:08X}\\n",\n                i, s.r1, s.r2, s.r3, s.r4, s.r5, s.r12, s.lr, s.host_pc);\n            pnp::trace_file_write(line.as_bytes());\n        }\n'''
    need(anchor in t,'FASTCALL export anchor missing')
    add=r'''        line.clear();
        let _=write!(line,"fastdiv751,index,a_div,s_div,mask\n");
        pnp::trace_file_write(line.as_bytes());
        for i in 0..fast_shown {
            let (a_div,s_div,mask)=super::hook::endpoint_fast_tail_div_v751(i);
            line.clear();
            let _=write!(line,"FASTDIV751,{},{:02X},{:02X},{:02X}\n",i,a_div,s_div,mask);
            pnp::trace_file_write(line.as_bytes());
        }
'''
    t=t.replace(anchor,anchor+add,1)

H.write_text(h); T.write_text(t)
print('Applied Suicune v7.5.1 direct final Random 2F60/2F68 rDIV capture')
