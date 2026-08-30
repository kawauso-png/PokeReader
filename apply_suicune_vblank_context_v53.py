#!/usr/bin/env python3
from pathlib import Path

hook_path = Path("reader_core/src/crystal/hook.rs")
trace_path = Path("reader_core/src/crystal/trace.rs")
h = hook_path.read_text()
t = trace_path.read_text()


def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return src.replace(old, new, 1)

# v5.2 returned a ~180-byte snapshot struct by value. Hardware traces 0044/0045
# showed every returned field as zero even though the ordinary VBlank hook
# fields (ADIV/ASUB/ATICK) were live. v5.3 keeps the old type for build
# compatibility but adds independent scalar/array storage and getters so no
# large struct assignment or large struct return is involved in the test path.
h = rep(
    h,
    '''static mut LAST_VBLANK_CONTEXT: VBlankContextSnapshot = VBlankContextSnapshot::EMPTY;
static mut VBLANK_CONTEXT_CAPTURE_ENABLED: bool = true;

pub fn latest_vblank_context() -> VBlankContextSnapshot {
    unsafe { LAST_VBLANK_CONTEXT }
}

pub fn set_vblank_context_capture(enabled: bool) {
    unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED = enabled; }
}''',
    '''static mut LAST_VBLANK_CONTEXT: VBlankContextSnapshot = VBlankContextSnapshot::EMPTY;
static mut VBLANK_CONTEXT_CAPTURE_ENABLED: bool = true;

// v5.3 split storage.  Keep every diagnostic independent so one trace tells us
// whether the rDIV branch fired, whether the gate was open, and whether the
// direct context copy completed.
static mut V53_HITS: u32 = 0;
static mut V53_WRITES: u32 = 0;
static mut V53_VALID: u8 = 0;
static mut V53_COMPLETE: u8 = 0;
static mut V53_CTX_MAPPED: u8 = 0;
static mut V53_PC: u16 = 0;
static mut V53_ADVANCE: u32 = 0;
static mut V53_DIV: u8 = 0;
static mut V53_MCYCLE: u8 = 0;
static mut V53_HOST_TICK: u64 = 0;
static mut V53_CPU_CTX: [u8; VBLANK_CTX_LEN] = [0; VBLANK_CTX_LEN];
static mut V53_REGS: [u32; VBLANK_ARM_REGS] = [0; VBLANK_ARM_REGS];
static mut V53_STACK: [u32; VBLANK_STACK_WORDS] = [0; VBLANK_STACK_WORDS];

pub fn latest_vblank_context() -> VBlankContextSnapshot {
    unsafe { LAST_VBLANK_CONTEXT }
}

pub fn set_vblank_context_capture(enabled: bool) {
    unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED = enabled; }
}

pub fn v53_vblank_hits() -> u32 { unsafe { V53_HITS } }
pub fn v53_vblank_writes() -> u32 { unsafe { V53_WRITES } }
pub fn v53_vblank_valid() -> u8 { unsafe { V53_VALID } }
pub fn v53_vblank_complete() -> u8 { unsafe { V53_COMPLETE } }
pub fn v53_vblank_ctx_mapped() -> u8 { unsafe { V53_CTX_MAPPED } }
pub fn v53_vblank_pc() -> u16 { unsafe { V53_PC } }
pub fn v53_vblank_advance() -> u32 { unsafe { V53_ADVANCE } }
pub fn v53_vblank_div() -> u8 { unsafe { V53_DIV } }
pub fn v53_vblank_mcycle() -> u8 { unsafe { V53_MCYCLE } }
pub fn v53_vblank_tick() -> u64 { unsafe { V53_HOST_TICK } }

pub fn v53_copy_vblank_arrays(
    cpu_ctx: &mut [u8; VBLANK_CTX_LEN],
    regs: &mut [u32; VBLANK_ARM_REGS],
    stack: &mut [u32; VBLANK_STACK_WORDS],
) {
    unsafe {
        for i in 0..VBLANK_CTX_LEN { cpu_ctx[i] = V53_CPU_CTX[i]; }
        for i in 0..VBLANK_ARM_REGS { regs[i] = V53_REGS[i]; }
        for i in 0..VBLANK_STACK_WORDS { stack[i] = V53_STACK[i]; }
    }
}''',
    "add v53 split storage",
)

old_capture = '''        if unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED } {
        let cpu_ctx = pnp::read_array::<VBLANK_CTX_LEN>(CRYSTAL_CPU_CTX_BASE);
        let mut saved_regs = [0u32; VBLANK_ARM_REGS];
        for (dst, src) in saved_regs.iter_mut().zip(regs.iter().take(VBLANK_ARM_REGS)) {
            *dst = *src;
        }
        let mut saved_stack = [0u32; VBLANK_STACK_WORDS];
        unsafe {
            for (i, slot) in saved_stack.iter_mut().enumerate() {
                *slot = core::ptr::read_volatile(_stack_pointer.add(i));
            }
            LAST_VBLANK_CONTEXT = VBlankContextSnapshot {
                valid: 1,
                pc,
                advance: RNG_ADVANCE.wrapping_add(1),
                div,
                mcycle,
                host_tick,
                cpu_ctx,
                regs: saved_regs,
                stack: saved_stack,
            };
        }
        }
'''
new_capture = '''        unsafe { V53_HITS = V53_HITS.wrapping_add(1); }
        if unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED } {
            unsafe {
                V53_WRITES = V53_WRITES.wrapping_add(1);
                V53_VALID = 1;
                V53_COMPLETE = 0;
                V53_PC = pc;
                V53_ADVANCE = RNG_ADVANCE.wrapping_add(1);
                V53_DIV = div;
                V53_MCYCLE = mcycle;
                V53_HOST_TICK = host_tick;
                V53_CTX_MAPPED = pnp::is_memory_mapped(CRYSTAL_CPU_CTX_BASE) as u8;

                // Directly write the static buffers.  No 180-byte temporary and
                // no 180-byte struct assignment on the ARM hook stack.
                let cpu_ptr = core::ptr::addr_of_mut!(V53_CPU_CTX).cast::<u8>();
                pnp::read_into_raw(CRYSTAL_CPU_CTX_BASE, cpu_ptr, VBLANK_CTX_LEN);
                for i in 0..VBLANK_ARM_REGS {
                    V53_REGS[i] = if i < regs.len() { regs[i] } else { 0 };
                }
                for i in 0..VBLANK_STACK_WORDS {
                    V53_STACK[i] = core::ptr::read_volatile(_stack_pointer.add(i));
                }
                V53_COMPLETE = 1;
            }
        }
'''
h = rep(h, old_capture, new_capture, "replace v52 capture with split capture")

# Replace the v5.2 large-struct return at Y+X with scalar getters + array copy.
old_arm = '''        let vb = latest_vblank_context();
        self.startsig_pc = vb.pc;
        self.startsig_cpu_ctx = vb.cpu_ctx;
        self.startsig_vb_valid = vb.valid;
        self.startsig_vb_advance = vb.advance;
        self.startsig_vb_div = vb.div;
        self.startsig_vb_mcycle = vb.mcycle;
        self.startsig_vb_tick = vb.host_tick;
        self.startsig_vb_regs = vb.regs;
        self.startsig_vb_stack = vb.stack;
        set_vblank_context_capture(false);'''
new_arm = '''        self.startsig_pc = v53_vblank_pc();
        self.startsig_vb_valid = v53_vblank_valid();
        self.startsig_vb_advance = v53_vblank_advance();
        self.startsig_vb_div = v53_vblank_div();
        self.startsig_vb_mcycle = v53_vblank_mcycle();
        self.startsig_vb_tick = v53_vblank_tick();
        v53_copy_vblank_arrays(
            &mut self.startsig_cpu_ctx,
            &mut self.startsig_vb_regs,
            &mut self.startsig_vb_stack,
        );
        set_vblank_context_capture(false);'''
t = rep(t, old_arm, new_arm, "use scalar v53 getters")

# Extend imports.  Keep latest_vblank_context imported only if generated code
# still references it elsewhere; v5.3 itself does not.
needle = 'latest_vblank_context,'
if needle not in t:
    raise SystemExit("latest_vblank_context import not found")
t = t.replace(
    needle,
    '''latest_vblank_context, v53_copy_vblank_arrays, v53_vblank_advance, v53_vblank_complete,
    v53_vblank_ctx_mapped, v53_vblank_div, v53_vblank_hits, v53_vblank_mcycle,
    v53_vblank_pc, v53_vblank_tick, v53_vblank_valid, v53_vblank_writes,''',
    1,
)

# Self-diagnosing CSV row.  The counters are read while capture is frozen, so
# they correspond to the pre-Target rolling period and cannot change mid-save.
t = rep(
    t,
    '"start_signature,status,target_pc,cpu_ctx_base,cpu_ctx_len,vblank_valid,vblank_advance,vblank_div,vblank_mcycle,vblank_tick,ctx_f604,cpu_ctx_hex,arm_regs_hex,host_stack_hex\\n"',
    '"start_signature,status,target_pc,cpu_ctx_base,cpu_ctx_len,vblank_valid,vblank_advance,vblank_div,vblank_mcycle,vblank_tick,ctx_f604,vblank_hits,vblank_writes,vblank_complete,ctx_mapped,cpu_ctx_hex,arm_regs_hex,host_stack_hex\\n"',
    "extend v53 startsig header",
)

t = rep(
    t,
    '''                "STARTSIG,V52,{:04X},{:08X},{},{},{},{:02X},{:02X},{},{:02X},",
                self.startsig_pc,
                STARTSIG_CPU_CTX_BASE,
                STARTSIG_CPU_CTX_LEN,
                self.startsig_vb_valid,
                self.startsig_vb_advance,
                self.startsig_vb_div,
                self.startsig_vb_mcycle,
                self.startsig_vb_tick,
                self.startsig_cpu_ctx[0x24]
            );''',
    '''                "STARTSIG,V53,{:04X},{:08X},{},{},{},{:02X},{:02X},{},{:02X},{},{},{},{},",
                self.startsig_pc,
                STARTSIG_CPU_CTX_BASE,
                STARTSIG_CPU_CTX_LEN,
                self.startsig_vb_valid,
                self.startsig_vb_advance,
                self.startsig_vb_div,
                self.startsig_vb_mcycle,
                self.startsig_vb_tick,
                self.startsig_cpu_ctx[0x24],
                v53_vblank_hits(),
                v53_vblank_writes(),
                v53_vblank_complete(),
                v53_vblank_ctx_mapped()
            );''',
    "write v53 diagnostics",
)

hook_path.write_text(h)
trace_path.write_text(t)
print("Applied Suicune VBlank Context v5.3 scalar diagnostics")
