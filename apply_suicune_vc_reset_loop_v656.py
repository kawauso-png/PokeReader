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

# v6.5.7: make both short-horizon retry failures friendly to the VC reset.
# ERR2 = current PRE prototype unsupported by the safe donor model.
# ERR3 = no shiny candidate in the current 12k horizon.
# Neither benefits from trapping the title in PokeReader's pause loop, so show
# a reset-specific status and release the host pause. The user can immediately
# use the VC software reset. A later Y+Down search clears queue/error/probe
# state, and after ~17 VBlanks the PRE ring is entirely from the new VC boot.

# C host-side resume request, paired with the generated host_request_pause().
# Earlier patches change whitespace/signature style, so identify the function
# semantically instead of depending on an exact text block.
if "void host_request_resume(void)" not in mainc:
    pause_matches = list(re.finditer(
        r"void\s+host_request_pause\s*\(\s*(?:void\s*)?\)\s*\{.*?is_paused\s*=\s*true\s*;.*?\}",
        mainc,
        flags=re.S,
    ))
    if len(pause_matches) != 1:
        occurrences = mainc.count("host_request_pause")
        raise SystemExit(
            f"v6.5.7 host_request_pause semantic match count: {len(pause_matches)}; name occurrences={occurrences}"
        )
    m = pause_matches[0]
    resume_fn = """

// Rust uses this only for reset-friendly search failures (ERR2 / ERR3).
// It does not inject any game input; it merely leaves PokeReader's own pause
// loop so the VC software reset can be used normally.
void host_request_resume(void)
{
    is_paused = false;
    fixed_frames_remaining = 0;
    fixed_run_pending = false;
}
"""
    mainc = mainc[:m.end()] + resume_fn + mainc[m.end():]

# Rust FFI declaration + test stub.
if "pub fn host_request_resume();" not in bind:
    anchor = "    pub fn host_request_pause();\n"
    if bind.count(anchor) != 1:
        raise SystemExit(f"v6.5.7 bindings pause declaration count: {bind.count(anchor)}")
    bind = bind.replace(anchor, anchor + "    pub fn host_request_resume();\n", 1)

if "pub extern \"C\" fn host_request_resume()" not in bind:
    anchor = """    #[no_mangle]\n    pub extern \"C\" fn host_request_pause() {}\n"""
    if bind.count(anchor) != 1:
        raise SystemExit(f"v6.5.7 bindings pause stub count: {bind.count(anchor)}")
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

# ERR2 and ERR3 are both retry-by-new-boot conditions. Release pause at the
# exact assignment/return site while keeping the error value latched for UI.
for code in (2, 3):
    needle = f"self.practical_search_error = {code};"
    if trace.count(needle) != 1:
        raise SystemExit(f"v6.5.7 ERR{code} assignment count: {trace.count(needle)}")
    pos = trace.find(needle)
    window = trace[pos:pos + 300]
    if "pnp::request_resume();" not in window:
        m = re.search(
            rf"self\.practical_search_error\s*=\s*{code};\s*\n(?P<indent>\s*)return;",
            trace[pos:pos + 300],
        )
        if not m:
            raise SystemExit(f"v6.5.7 ERR{code} return anchor not found")
        old = m.group(0)
        indent = m.group("indent")
        new = f"self.practical_search_error = {code};\n{indent}pnp::request_resume();\n{indent}return;"
        trace = trace[:pos] + trace[pos:].replace(old, new, 1)

# Give ERR2/ERR3 a user-facing reset instruction instead of the generic label.
status_old = """        } else if self.practical_search_error != 0 {\n            pnp::println!(\"S64 ERR {} K{}\", self.practical_search_error, self.practical_search_skipped);\n"""
if "S65 RESET VC E{}" not in trace:
    if trace.count(status_old) != 1:
        raise SystemExit(f"v6.5.7 generic error status anchor count: {trace.count(status_old)}")
    status_new = """        } else if self.practical_search_error == 2 || self.practical_search_error == 3 {\n            pnp::println!(\"S65 RESET VC E{}\", self.practical_search_error);\n        } else if self.practical_search_error != 0 {\n            pnp::println!(\"S64 ERR {} K{}\", self.practical_search_error, self.practical_search_skipped);\n"""
    trace = trace.replace(status_old, status_new, 1)

# Sanity checks: exactly ERR2/ERR3 auto-resume. READY/path execution, ERR4,
# cadence diagnostics and hard MISS guards remain untouched.
if trace.count("pnp::request_resume();") != 2:
    raise SystemExit(f"v6.5.7 request_resume call count: {trace.count('pnp::request_resume();')}")
if "S65 RESET VC E{}" not in trace:
    raise SystemExit("v6.5.7 reset status missing")
if "self.practical_search_error = 15;" not in trace:
    raise SystemExit("v6.5.7 cadence ERR15 marker missing")
if "self.practical_fail(fail)" not in trace:
    raise SystemExit("v6.5.7 hard MISS handler missing")

main_path.write_text(mainc)
bind_path.write_text(bind)
pnp_hook_path.write_text(pnph)
trace_path.write_text(trace)

print("Applied Suicune v6.5.7 VC-reset retry loop: ERR2/ERR3 -> RESET VC + host resume")
