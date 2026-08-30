#!/usr/bin/env python3
from pathlib import Path


def repl(path, old, new, label):
    p = Path(path)
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    p.write_text(s.replace(old, new, 1))


hook = "reader_core/src/crystal/hook.rs"
trace = "reader_core/src/crystal/trace.rs"

repl(
    hook,
    "static mut GB_READ_MEM_HOOK: u32 = 0x1af17c;",
    """static mut GB_READ_MEM_HOOK: u32 = 0x1af17c;
static mut GB_READ_HOOK_WORD: u32 = 0;
static mut GB_READ_HOOK_RET: u32 = 0;

pub fn gb_read_hook_word() -> u32 {
    unsafe { GB_READ_HOOK_WORD }
}

pub fn gb_read_hook_ret() -> u32 {
    unsafe { GB_READ_HOOK_RET }
}""",
    "insert GB read hook diagnostics",
)

repl(
    hook,
    """    utils::hook_game_branch!(
        game_name = crystal,""",
    """    unsafe { GB_READ_HOOK_WORD = pnp::read::<u32>(GB_READ_MEM_HOOK) };

    utils::hook_game_branch!(
        game_name = crystal,""",
    "capture original GB read BL",
)

repl(
    hook,
    "    unsafe { CYC_HOOK_RET = update_cycle_counter::return_addr };\n}",
    """    unsafe { CYC_HOOK_RET = update_cycle_counter::return_addr };
    unsafe { GB_READ_HOOK_RET = gb_read_mem::return_addr };
}""",
    "capture original GB read target",
)

repl(
    trace,
    "    call_log_start, call_log_stop, cyc_hook_ret, cyc_hook_word, cycle_counter, deep_log_clear,",
    "    call_log_start, call_log_stop, cyc_hook_ret, cyc_hook_word, cycle_counter, deep_log_clear,\n    gb_read_hook_ret, gb_read_hook_word,",
    "import GB read diagnostics",
)

repl(
    trace,
    """        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();""",
    """        pnp::trace_file_write(line.as_bytes());

        let gb_word = gb_read_hook_word();
        let gb_ret = gb_read_hook_ret();
        line.clear();
        let _ = write!(line, \"ARM_GBREAD_META,001AF11C,{:08X},{:08X}\\n\", gb_word, gb_ret);
        pnp::trace_file_write(line.as_bytes());

        if gb_ret != 0 && pnp::is_memory_mapped(gb_ret) {
            let arm_target = pnp::read_array::<256>(gb_ret);
            line.clear();
            let _ = write!(line, \"ARM_GBREAD_TARGET,{:08X},\", gb_ret);
            for byte in arm_target.iter() {
                let _ = write!(line, \"{:02X}\", byte);
            }
            let _ = write!(line, \"\\n\");
            pnp::trace_file_write(line.as_bytes());
        }

        pnp::trace_file_close();""",
    "dump original GB read helper",
)

print("Applied v4.1.1 original GB rDIV helper diagnostics")
