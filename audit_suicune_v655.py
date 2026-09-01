#!/usr/bin/env python3
from pathlib import Path

trace = Path("reader_core/src/crystal/trace.rs").read_text()
practical = Path("reader_core/src/crystal/practical.rs").read_text()
mainc = Path("3gx/sources/main.c").read_text()
bindings = Path("reader_core/src/pnp/bindings.rs").read_text()
pnphook = Path("reader_core/src/pnp/hook.rs").read_text()

def require(cond, msg):
    if not cond:
        raise SystemExit("AUDIT FAIL: " + msg)

# 12k must be the executable shiny-search horizon; old long-horizon literals
# must not return just because TEST mode can bypass search entirely.
require("12000" in practical or "12000" in trace, "12,000F horizon marker missing")
require("131072" not in practical and "0x20000" not in practical and "0x00020000" not in practical,
        "old 131072F horizon still present in practical.rs")

# Search-start state must be reusable after an error or VC reset.
for marker in [
    "self.practical_search_error = 0;",
    "self.practical_search_skipped = 0;",
    "self.practical_search_index = 0;",
    "self.practical_search_count = 0;",
]:
    require(marker in trace, f"search reset marker missing: {marker}")

# PRE pause-boundary compensation must exist both at search start and target time.
require("pre_lag > 1" in trace, "search-start PRE lag guard missing")
require("pre_lag == 1" in trace, "search-start PRE +1 rotation compensation missing")
require("let lag = current.wrapping_sub(last_advance);" in trace, "target-time PRE lag compensation missing")
require("if lag > 1" in trace and "if lag == 1" in trace, "target-time PRE lag guard/rotation missing")

# ERR2 and cadence failure must remain distinct.
require("self.practical_search_error = 2;" in trace, "unsupported PRE ERR2 marker missing")
require("self.practical_search_error = 15;" in trace, "cadence failure is not ERR15")

# Target time must re-evaluate actual state/DIV rather than require projected equality.
require("practical::evaluate(lane_id, reader.rng_state(), measured_div())" in trace,
        "live root is not re-evaluated at candidate target")
require("let root_ok = reader.rng_state() == self.practical_states[idx]" not in trace,
        "old exact projected root gate still present")

# Queue exhaustion after an actual waited candidate remains a hard pause.
needle = "self.practical_search_error = 4;\n            pnp::request_pause();"
require(trace.count(needle) >= 2, "ERR4 queue exhaustion does not pause on both paths")

# rel40 mismatch must learn, not terminate the probe.
rel40 = trace.find("if rel == 40 && !self.practical_checked40")
rel716 = trace.find("else if rel == 716 && !self.practical_checked716", rel40)
require(rel40 >= 0 and rel716 > rel40, "rel40/716 path-check block missing")
block40 = trace[rel40:rel716]
require("self.practical_miss = 1;" in block40, "rel40 mismatch does not enter LEARN")
require("practical_fail" not in block40 and "fail = 1" not in block40,
        "rel40 still terminates as hard MISS")

# Late path checks must still be hard guards.
rel717 = trace.find("else if rel == 717 && !self.practical_checked717", rel716)
require(rel717 > rel716, "rel717 path-check block missing")
late = trace[rel716:rel717 + 800]
require("fail = 2" in late and "fail = 3" in late, "rel716/717 hard MISS guards missing")
require("self.practical_fail(fail)" in trace, "hard MISS handler missing")

# UI must distinguish adaptive learn/search diagnostics and the direct TEST path.
for marker in [
    "S65 LEARN 1", "S65 MISS {}", "S64 ERR {} K{}", "S64 WAIT", "S64 READY",
    "S65 RESET VC E{}", "S658 TEST",
]:
    require(marker in trace, f"status marker missing: {marker}")

# ERR2 and ERR3 remain immediate reset opportunities in shiny-search mode.
for code in (2, 3):
    pos = trace.find(f"self.practical_search_error = {code};")
    require(pos >= 0, f"ERR{code} assignment missing")
    block = trace[pos:pos + 300]
    require("pnp::request_resume();" in block, f"ERR{code} does not release host pause")
require(trace.count("pnp::request_resume();") == 2, "automatic resume leaked outside ERR2/ERR3")
require("void host_request_resume(void)" in mainc, "C host resume function missing")
require("pub fn host_request_resume();" in bindings, "Rust FFI host resume declaration missing")
require("pub fn request_resume()" in pnphook, "PNP request_resume wrapper missing")

# v6.5.8 Fast Validate: the user supplies only physical UP plus a B tap. B is
# consumed while paused and must be released before any exact game frame.
require("// v6.5.8 FastValidate: hold UP and tap B; no Y/X chord." in mainc,
        "FastValidate B trigger marker missing")
require(mainc.count("(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)") == 1,
        "FastValidate UP+B trigger missing or duplicated")
require("if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)" in mainc,
        "B is not gated out before Exact-2F")
require("if ((held & (KEY_DUP | KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)" in mainc,
        "B is not gated in post-2F auto resume")
require("suicune_auto_resume_pending && !(held & KEY_DUP)" in mainc,
        "physical-UP safety abort missing")
require(mainc.count("arm_suicune_probe();") >= 2,
        "FastValidate B path does not arm Deep Probe")

# The old Y+X path remains as a fallback, and Y+B legacy plumbing must not be
# accidentally hijacked by the new B trigger (the new condition requires !Y).
require("if (just_pressed & KEY_X)" in mainc, "legacy Y+X fallback missing")
require("!(held & KEY_Y)" in mainc, "FastValidate does not protect Y+B command")

# Search hotkey must remain present.
require("KEY_DDOWN" in mainc or "KEY_DOWN" in mainc, "Down key handling missing from C pause loop")
require("KEY_Y" in mainc, "Y modifier handling missing from C pause loop")

print("AUDIT PASS: v6.5.8 12k + learning + reset + UP+B FastValidate invariants verified")
