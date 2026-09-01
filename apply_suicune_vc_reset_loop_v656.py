#!/usr/bin/env python3
from pathlib import Path
import re

main_path = Path("3gx/sources/main.c")
bind_path = Path("reader_core/src/pnp/bindings.rs")
pnp_hook_path = Path("reader_core/src/pnp/hook.rs")
trace_path = Path("reader_core/src/crystal/trace.rs")

mainc = main_path.read_text()
bind = bind_path.read_text()
pnph = pnp_hook_path.read_text()
trace = trace_path.read_text()

# v6.5.6: make the short-horizon retry loop friendly to the VC's own reset.
# When a 12k search has no candidate (ERR3), do not strand the title inside
# PokeReader's pause loop. Show a reset-specific status and release the pause,
# so the user can immediately use the VC software reset UI. The next Y+Down
# search already clears queue/error/probe state, and after ~17 VBlanks the PRE
# ring is entirely from the new VC boot.

# C host-side resume request, paired with the existing host_request_pause().
if "void host_request_resume(void)" not in mainc:
    anchor = """void host_request_pause(void)\n{\n    is_paused = true;\n}\n"""
    if mainc.count(anchor) != 1:
        raise SystemExit(f"v6.5.6 host_request_pause anchor count: {mainc.count(anchor)}")
    repl = anchor + """

// Rust uses this only for reset-friendly search failures (currently ERR3).
// It does not inject any game input; it merely leaves PokeReader's own pause
// loop so the VC software reset can be used normally.
void host_request_resume(void)
{
    is_paused = false;
    fixed_frames_remaining = 0;
    fixed_run_pending = false;
}
"""
    mainc = mainc.replace(anchor, repl, 1)

# Rust FFI declaration + test stub.
if "pub fn host_request_resume();" not in bind:
    anchor = "    pub fn host_request_pause();\n"
    if bind.count(anchor) != 1:
        raise SystemExit(f"v6.5.6 bindings pause declaration count: {bind.count(anchor)}")
    bind = bind.replace(anchor, anchor + "    pub fn host_request_resume();\n", 1)

if "pub extern \"C\" fn host_request_resume()" not in bind:
    anchor = """    #[no_mangle]\n    pub extern \"C\" fn host_request_pause() {}\n"""
    if bind.count(anchor) != 1:
        raise SystemExit(f"v6.5.6 bindings pause stub count: {bind.count(anchor)}")
    bind = bind.replace(
        anchor,
        anchor + """    #[no_mangle]\n    pub extern \"C\" fn host_request_resume() {}\n""",
        1,
    )

# Public PNP wrapper. pnp::hook is re-exported from pnp::mod.
if "pub fn request_resume()" not in pnph:
    pnph += """

/// Leave PokeReader's host pause loop without injecting any game key.
pub fn request_resume() {
    unsafe { bindings::host_request_resume() }
}
"""

# ERR3 is the unique "no candidate in current 12k horizon" result. Release
# pause at the exact point it is raised. Keep the error value latched so the
# overlay can explain why the title resumed.
needle = "self.practical_search_error = 3;"
if trace.count(needle) != 1:
    raise SystemExit(f"v6.5.6 ERR3 assignment count: {trace.count(needle)}")
pos = trace.find(needle)
window = trace[pos:pos + 220]
if "pnp::request_resume();" not in window:
    m = re.search(r"self\.practical_search_error = 3;\n(?P<indent>\s*)return;", trace[pos:pos + 220])
    if not m:
        raise SystemExit("v6.5.6 ERR3 return anchor not found")
    old = m.group(0)
    indent = m.group("indent")
    new = f"self.practical_search_error = 3;\n{indent}pnp::request_resume();\n{indent}return;"
    trace = trace[:pos] + trace[pos:].replace(old, new, 1)

# Give ERR3 a user-facing reset instruction instead of the generic ERR label.
status_old = """        } else if self.practical_search_error != 0 {\n            pnp::println!(\"S64 ERR {} K{}\", self.practical_search_error, self.practical_search_skipped);\n"""
if "S65 RESET VC" not in trace:
    if trace.count(status_old) != 1:
        raise SystemExit(f"v6.5.6 generic error status anchor count: {trace.count(status_old)}")
    status_new = """        } else if self.practical_search_error == 3 {\n            pnp::println!(\"S65 RESET VC\");\n        } else if self.practical_search_error != 0 {\n            pnp::println!(\"S64 ERR {} K{}\", self.practical_search_error, self.practical_search_skipped);\n"""
    trace = trace.replace(status_old, status_new, 1)

# Sanity checks: only ERR3 gets automatic host resume. READY/path execution
# and hard MISS guards remain untouched.
if trace.count("pnp::request_resume();") != 1:
    raise SystemExit(f"v6.5.6 request_resume call count: {trace.count('pnp::request_resume();')}")
if "S65 RESET VC" not in trace:
    raise SystemExit("v6.5.6 reset status missing")
if "self.practical_search_error = 15;" not in trace:
    raise SystemExit("v6.5.6 cadence ERR15 marker missing")
if "self.practical_fail(fail)" not in trace:
    raise SystemExit("v6.5.6 hard MISS handler missing")

main_path.write_text(mainc)
bind_path.write_text(bind)
pnp_hook_path.write_text(pnph)
trace_path.write_text(trace)

print("Applied Suicune v6.5.6 VC-reset retry loop: ERR3 -> RESET VC + host resume")
