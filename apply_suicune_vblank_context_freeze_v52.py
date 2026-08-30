#!/usr/bin/env python3
from pathlib import Path

hook_path = Path("reader_core/src/crystal/hook.rs")
trace_path = Path("reader_core/src/crystal/trace.rs")
h = hook_path.read_text()
t = trace_path.read_text()

def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return src.replace(old, new, 1)

h = rep(h,
'''static mut LAST_VBLANK_CONTEXT: VBlankContextSnapshot = VBlankContextSnapshot::EMPTY;

pub fn latest_vblank_context() -> VBlankContextSnapshot {
    unsafe { LAST_VBLANK_CONTEXT }
}''',
'''static mut LAST_VBLANK_CONTEXT: VBlankContextSnapshot = VBlankContextSnapshot::EMPTY;
static mut VBLANK_CONTEXT_CAPTURE_ENABLED: bool = true;

pub fn latest_vblank_context() -> VBlankContextSnapshot {
    unsafe { LAST_VBLANK_CONTEXT }
}

pub fn set_vblank_context_capture(enabled: bool) {
    unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED = enabled; }
}''',
"add vblank capture gate")

h = rep(h,
'''        let cpu_ctx = pnp::read_array::<VBLANK_CTX_LEN>(CRYSTAL_CPU_CTX_BASE);
        let mut saved_regs = [0u32; VBLANK_ARM_REGS];''',
'''        if unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED } {
        let cpu_ctx = pnp::read_array::<VBLANK_CTX_LEN>(CRYSTAL_CPU_CTX_BASE);
        let mut saved_regs = [0u32; VBLANK_ARM_REGS];''',
"open capture gate")

h = rep(h,
'''            LAST_VBLANK_CONTEXT = VBlankContextSnapshot {
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

        if ENABLE_DIFF_PROBE {''',
'''            LAST_VBLANK_CONTEXT = VBlankContextSnapshot {
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

        if ENABLE_DIFF_PROBE {''',
"close capture gate")

# Add setter import to whichever generated hook import block v5.2 produced.
if "set_vblank_context_capture" not in t:
    start = t.find("use super::hook::{")
    if start < 0:
        raise SystemExit("hook import block not found")
    end = t.find("};", start)
    t = t[:end] + "    set_vblank_context_capture,\n" + t[end:]

# Freeze immediately after copying the Target rolling sample. No heavy context
# reads occur during Exact2F/event/stop2/tail.
t = rep(t,
'''        self.startsig_vb_regs = vb.regs;
        self.startsig_vb_stack = vb.stack;
        self.probe_target = ProbeTarget {''',
'''        self.startsig_vb_regs = vb.regs;
        self.startsig_vb_stack = vb.stack;
        set_vblank_context_capture(false);
        self.probe_target = ProbeTarget {''',
"freeze capture at target")

# Re-enable only after the result CSV is fully closed, so the next trial can
# accumulate fresh pre-Target snapshots without affecting this trial's DV.
t = rep(t,
'''        pnp::trace_file_close();
        self.save_index += 1;
        self.save_result = Some(true);''',
'''        pnp::trace_file_close();
        set_vblank_context_capture(true);
        self.save_index += 1;
        self.save_result = Some(true);''',
"reenable capture after save")

hook_path.write_text(h)
trace_path.write_text(t)
print("Applied v5.2 Target-freeze capture gate")
