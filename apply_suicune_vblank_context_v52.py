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

# -------------------------------------------------------------------------
# Keep one rolling snapshot at the first VBlank rDIV read.  This is the exact
# observation point that already produces Target ADIV/ASUB/ATICK.  v4.8 tried
# to read the emulator CPU context later while the game was frozen and got an
# all-zero block on hardware.  v5.2 snapshots it while the proven rDIV hook is
# actually executing, then Y+X merely copies the last completed sample.
# -------------------------------------------------------------------------
h = rep(
    h,
    '''static mut STICKS: u64 = 0;\n\n// Diagnostics for the legacy cycle hook.''',
    '''static mut STICKS: u64 = 0;\n\n// Suicune VBlank Context v5.2.  One 64-byte emulator-context memcpy plus the\n// ARM hook registers/stack at VBlank-A.  This is rolling state only; saving a\n// trace later does not add any work to rel1..DV.\npub const VBLANK_CTX_LEN: usize = 64;\npub const VBLANK_ARM_REGS: usize = 15;\npub const VBLANK_STACK_WORDS: usize = 8;\n\n#[derive(Clone, Copy)]\npub struct VBlankContextSnapshot {\n    pub valid: u8,\n    pub pc: u16,\n    pub advance: u32,\n    pub div: u8,\n    pub mcycle: u8,\n    pub host_tick: u64,\n    pub cpu_ctx: [u8; VBLANK_CTX_LEN],\n    pub regs: [u32; VBLANK_ARM_REGS],\n    pub stack: [u32; VBLANK_STACK_WORDS],\n}\n\nimpl VBlankContextSnapshot {\n    const EMPTY: Self = Self {\n        valid: 0, pc: 0, advance: 0, div: 0, mcycle: 0, host_tick: 0,\n        cpu_ctx: [0; VBLANK_CTX_LEN],\n        regs: [0; VBLANK_ARM_REGS],\n        stack: [0; VBLANK_STACK_WORDS],\n    };\n}\n\nstatic mut LAST_VBLANK_CONTEXT: VBlankContextSnapshot = VBlankContextSnapshot::EMPTY;\n\npub fn latest_vblank_context() -> VBlankContextSnapshot {\n    unsafe { LAST_VBLANK_CONTEXT }\n}\n\n// Diagnostics for the legacy cycle hook.''',
    "insert vblank context state",
)

h = rep(
    h,
    '''    if RNG_DIV_READ_1.contains(&pc) {\n        let div = reader.div();\n        if ENABLE_DIFF_PROBE {''',
    '''    if RNG_DIV_READ_1.contains(&pc) {\n        let div = reader.div();\n\n        // Capture while the GB CPU is already stopped inside the rDIV hook.\n        // The post-read advance is RNG_ADVANCE+1, matching ProbeTarget.advance\n        // when the user pauses on this presented Target frame.\n        let cpu_ctx = pnp::read_array::<VBLANK_CTX_LEN>(CRYSTAL_CPU_CTX_BASE);\n        let mut saved_regs = [0u32; VBLANK_ARM_REGS];\n        for (dst, src) in saved_regs.iter_mut().zip(regs.iter().take(VBLANK_ARM_REGS)) {\n            *dst = *src;\n        }\n        let mut saved_stack = [0u32; VBLANK_STACK_WORDS];\n        unsafe {\n            for (i, slot) in saved_stack.iter_mut().enumerate() {\n                *slot = core::ptr::read_volatile(_stack_pointer.add(i));\n            }\n            LAST_VBLANK_CONTEXT = VBlankContextSnapshot {\n                valid: 1,\n                pc,\n                advance: RNG_ADVANCE.wrapping_add(1),\n                div,\n                mcycle,\n                host_tick,\n                cpu_ctx,\n                regs: saved_regs,\n                stack: saved_stack,\n            };\n        }\n\n        if ENABLE_DIFF_PROBE {''',
    "capture rolling vblank context",
)

# -------------------------------------------------------------------------
# Trace: freeze the rolling sample at Y+X instead of reading 0x22F5E0 while
# paused.  Preserve the v4.8 field names so no other probe logic is disturbed.
# Add enough metadata to verify that the rolling sample really is the Target.
# -------------------------------------------------------------------------
t = rep(
    t,
    '''    sdiv_cycles, sdiv_subtick, sdiv_tick, sub_div_tracker,\n};''',
    '''    sdiv_cycles, sdiv_subtick, sdiv_tick, sub_div_tracker, latest_vblank_context,\n};''',
    "import latest vblank context",
)

t = rep(
    t,
    '''    startsig_pc: u16,\n    startsig_cpu_ctx: [u8; STARTSIG_CPU_CTX_LEN],\n    /// Row shown first in the on screen table.''',
    '''    startsig_pc: u16,\n    startsig_cpu_ctx: [u8; STARTSIG_CPU_CTX_LEN],\n    startsig_vb_valid: u8,\n    startsig_vb_advance: u32,\n    startsig_vb_div: u8,\n    startsig_vb_mcycle: u8,\n    startsig_vb_tick: u64,\n    startsig_vb_regs: [u32; 15],\n    startsig_vb_stack: [u32; 8],\n    /// Row shown first in the on screen table.''',
    "add frozen vblank fields",
)

t = rep(
    t,
    '''            startsig_pc: 0,\n            startsig_cpu_ctx: [0; STARTSIG_CPU_CTX_LEN],\n            cursor: 0,''',
    '''            startsig_pc: 0,\n            startsig_cpu_ctx: [0; STARTSIG_CPU_CTX_LEN],\n            startsig_vb_valid: 0,\n            startsig_vb_advance: 0,\n            startsig_vb_div: 0,\n            startsig_vb_mcycle: 0,\n            startsig_vb_tick: 0,\n            startsig_vb_regs: [0; 15],\n            startsig_vb_stack: [0; 8],\n            cursor: 0,''',
    "init frozen vblank fields",
)

t = rep(
    t,
    '''        self.startsig_pc = 0;\n        self.startsig_cpu_ctx = [0; STARTSIG_CPU_CTX_LEN];''',
    '''        self.startsig_pc = 0;\n        self.startsig_cpu_ctx = [0; STARTSIG_CPU_CTX_LEN];\n        self.startsig_vb_valid = 0;\n        self.startsig_vb_advance = 0;\n        self.startsig_vb_div = 0;\n        self.startsig_vb_mcycle = 0;\n        self.startsig_vb_tick = 0;\n        self.startsig_vb_regs = [0; 15];\n        self.startsig_vb_stack = [0; 8];''',
    "reset frozen vblank fields",
)

t = rep(
    t,
    '''        self.startsig_pc = reader.pc_reg();\n        unsafe {\n            pnp::read_into_raw(\n                STARTSIG_CPU_CTX_BASE,\n                self.startsig_cpu_ctx.as_mut_ptr(),\n                STARTSIG_CPU_CTX_LEN,\n            );\n        }\n        self.probe_target = ProbeTarget {''',
    '''        let vb = latest_vblank_context();\n        self.startsig_pc = vb.pc;\n        self.startsig_cpu_ctx = vb.cpu_ctx;\n        self.startsig_vb_valid = vb.valid;\n        self.startsig_vb_advance = vb.advance;\n        self.startsig_vb_div = vb.div;\n        self.startsig_vb_mcycle = vb.mcycle;\n        self.startsig_vb_tick = vb.host_tick;\n        self.startsig_vb_regs = vb.regs;\n        self.startsig_vb_stack = vb.stack;\n        self.probe_target = ProbeTarget {''',
    "use rolling context at target",
)

# Replace the v4.8 CSV section with a v5.2 self-validating row.
t = rep(
    t,
    '''            \"start_signature,status,target_pc,cpu_ctx_base,cpu_ctx_len,cpu_ctx_hex\\n\"''',
    '''            \"start_signature,status,target_pc,cpu_ctx_base,cpu_ctx_len,vblank_valid,vblank_advance,vblank_div,vblank_mcycle,vblank_tick,ctx_f604,cpu_ctx_hex,arm_regs_hex,host_stack_hex\\n\"''',
    "extend startsig header",
)

t = rep(
    t,
    '''                \"STARTSIG,V48,{:04X},{:08X},{},\",\n                self.startsig_pc,\n                STARTSIG_CPU_CTX_BASE,\n                STARTSIG_CPU_CTX_LEN\n            );\n            for byte in self.startsig_cpu_ctx.iter() {\n                let _ = write!(line, \"{:02X}\", byte);\n            }\n            let _ = write!(line, \"\\n\\n\");''',
    '''                \"STARTSIG,V52,{:04X},{:08X},{},{},{},{:02X},{:02X},{},{:02X},\",\n                self.startsig_pc,\n                STARTSIG_CPU_CTX_BASE,\n                STARTSIG_CPU_CTX_LEN,\n                self.startsig_vb_valid,\n                self.startsig_vb_advance,\n                self.startsig_vb_div,\n                self.startsig_vb_mcycle,\n                self.startsig_vb_tick,\n                self.startsig_cpu_ctx[0x24]\n            );\n            for byte in self.startsig_cpu_ctx.iter() {\n                let _ = write!(line, \"{:02X}\", byte);\n            }\n            let _ = write!(line, \",\");\n            for word in self.startsig_vb_regs.iter() {\n                let _ = write!(line, \"{:08X}\", word);\n            }\n            let _ = write!(line, \",\");\n            for word in self.startsig_vb_stack.iter() {\n                let _ = write!(line, \"{:08X}\", word);\n            }\n            let _ = write!(line, \"\\n\\n\");''',
    "write v52 startsig row",
)

hook_path.write_text(h)
trace_path.write_text(t)
print("Applied Suicune rolling VBlank Context v5.2")
