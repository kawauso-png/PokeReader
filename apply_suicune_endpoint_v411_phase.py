#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    s = path.read_text()
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{path}: {label}: expected exactly one match, got {count}")
    path.write_text(s.replace(old, new, 1))


hook = Path("reader_core/src/crystal/hook.rs")
trace = Path("reader_core/src/crystal/trace.rs")

# 0x22F600 and 0x22F604 are both passed around by the JP VC memory-read
# dispatcher. v4.1.1 logs F600 at every rDIV hook (02B6/02BE and 2F60/2F68)
# so the pair can be tested as the emulator's true sub-DIV timing state.
replace_once(
    hook,
    "const CRYSTAL_M_CYCLE_SUBTICK_ADDR: u32 = 0x0022f604;",
    "const CRYSTAL_M_CYCLE_SUBTICK_ADDR: u32 = 0x0022f604;\nconst CRYSTAL_PHASE_AUX_ADDR: u32 = 0x0022f600;",
    "add F600 address",
)

replace_once(
    hook,
    "    pub mcycle: u8,\n}",
    "    pub mcycle: u8,\n    pub phase_aux: u32,\n}",
    "add CallEntry phase_aux",
)

replace_once(
    hook,
    "    mcycle: 0,\n}; CALL_LOG_LEN];",
    "    mcycle: 0,\n    phase_aux: 0,\n}; CALL_LOG_LEN];",
    "init CallEntry phase_aux",
)

replace_once(
    hook,
    "    let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);\n\n    capture_deep_random",
    "    let mcycle = pnp::read::<u8>(CRYSTAL_M_CYCLE_SUBTICK_ADDR);\n    // One adjacent 32-bit value used by the same VC timing path. Keep this\n    // lightweight: unlike Deep Probe this is only one direct word read.\n    let phase_aux = pnp::read::<u32>(CRYSTAL_PHASE_AUX_ADDR);\n\n    capture_deep_random",
    "read F600",
)

replace_once(
    hook,
    "                mcycle,\n            };",
    "                mcycle,\n                phase_aux,\n            };",
    "store F600 in call log",
)

replace_once(
    trace,
    '            line, "\\ncall_index,pc,advance,add,sub,div,cycles,host_tick,mcycle\\n");',
    '            line, "\\ncall_index,pc,advance,add,sub,div,cycles,host_tick,mcycle,phase_aux_f600\\n");',
    "extend call CSV header",
)

replace_once(
    trace,
    '                "{},{:04X},{},{:02X},{:02X},{:04X},{},{},{:02X}\\n",',
    '                "{},{:04X},{},{:02X},{:02X},{:04X},{},{},{:02X},{:08X}\\n",',
    "extend call CSV format",
)

replace_once(
    trace,
    "                e.host_tick,\n                e.mcycle\n            );",
    "                e.host_tick,\n                e.mcycle,\n                e.phase_aux\n            );",
    "write F600 call field",
)

print("Applied Suicune Endpoint Probe v4.1.1 F600 phase logger")
