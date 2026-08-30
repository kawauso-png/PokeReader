#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
s = path.read_text()


def replace_once(old: str, new: str, label: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    s = s.replace(old, new, 1)


# v4.8 intentionally does NOT add any per-frame work.  Everything already
# needed to derive J27/rel40 is present in the ordinary frame CSV and the v3.8
# host timing footer.  The only genuinely new measurement is a one-shot raw
# emulator CPU-context snapshot taken while the game is frozen at the exact
# Y+X Target.  This cannot perturb the subsequent emulated execution because
# no game frame is allowed through until after the snapshot is complete.

replace_once(
    "const DEFAULT_WATCH: u32 = 0xd23d;",
    """const DEFAULT_WATCH: u32 = 0xd23d;

// Suicune Start Signature v4.8.  Deep Probe already established that the JP VC
// LR35902 CPU context lives around 0x22F5E0 and that the emulated PC is at
// +0x1C (0x22F5FC).  Snapshot the whole 64-byte context at the frozen Target so
// offline analysis can search for the hidden start variable that selects J27.
const STARTSIG_CPU_CTX_BASE: u32 = 0x0022f5e0;
const STARTSIG_CPU_CTX_LEN: usize = 64;""",
    "insert start signature constants",
)

replace_once(
    """    endpoint: EndpointSnapshot,
    endpoint_pause_requested: bool,
    /// Row shown first in the on screen table.""",
    """    endpoint: EndpointSnapshot,
    endpoint_pause_requested: bool,
    // v4.8 frozen-Target one-shot context. No sampling is performed after the
    // exact run begins, so the experiment does not add timing work to rel1..DV.
    startsig_pc: u16,
    startsig_cpu_ctx: [u8; STARTSIG_CPU_CTX_LEN],
    /// Row shown first in the on screen table.""",
    "add start signature fields",
)

replace_once(
    """            endpoint: EndpointSnapshot::default(),
            endpoint_pause_requested: false,
            cursor: 0,""",
    """            endpoint: EndpointSnapshot::default(),
            endpoint_pause_requested: false,
            startsig_pc: 0,
            startsig_cpu_ctx: [0; STARTSIG_CPU_CTX_LEN],
            cursor: 0,""",
    "init start signature fields",
)

replace_once(
    """        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;""",
    """        self.endpoint = EndpointSnapshot::default();
        self.endpoint_pause_requested = false;
        self.startsig_pc = 0;
        self.startsig_cpu_ctx = [0; STARTSIG_CPU_CTX_LEN];""",
    "reset start signature fields",
)

# v4.4 inserted endpoint_fast_tail_stop() immediately before probe_target.
# Capture after reset/clear while the emulator is still frozen in the pause loop.
replace_once(
    """        deep_log_clear();
        endpoint_fast_tail_stop();
        self.probe_target = ProbeTarget {""",
    """        deep_log_clear();
        endpoint_fast_tail_stop();
        self.startsig_pc = reader.pc_reg();
        unsafe {
            pnp::read_into_raw(
                STARTSIG_CPU_CTX_BASE,
                self.startsig_cpu_ctx.as_mut_ptr(),
                STARTSIG_CPU_CTX_LEN,
            );
        }
        self.probe_target = ProbeTarget {""",
    "capture frozen target cpu context",
)

# Preserve the established probe header for every existing parser.  Add a
# separate v4.8 section containing the raw context as one fixed-width hex cell.
replace_once(
    """            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );""",
    """            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

        let _ = write!(
            line,
            \"start_signature,status,target_pc,cpu_ctx_base,cpu_ctx_len,cpu_ctx_hex\\n\"
        );
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        if self.probe_session {
            let _ = write!(
                line,
                \"STARTSIG,V48,{:04X},{:08X},{},\",
                self.startsig_pc,
                STARTSIG_CPU_CTX_BASE,
                STARTSIG_CPU_CTX_LEN
            );
            for byte in self.startsig_cpu_ctx.iter() {
                let _ = write!(line, \"{:02X}\", byte);
            }
            let _ = write!(line, \"\\n\\n\");
        } else {
            let _ = write!(line, \"STARTSIG,NO_PROBE,,,,\\n\\n\");
        }
        pnp::trace_file_write(line.as_bytes());
        line.clear();

        let _ = write!(
            line,
            \"endpoint,status,stop2_advance,stop2_offset,expected_dv_advance,pause_advance,capture_advance,capture_offset,state,div,ap4,sp4,asub,ssub,atick,stick,keys\\n\"
        );""",
    "insert start signature csv section",
)

# Identify the build at the already-frozen Endpoint. This does not alter the
# running event before the point whose trajectory we are studying.
s = s.replace('"EP44 +{} S{:04X}"', '"EP48 +{} S{:04X}"')
if '"EP48 +{} S{:04X}"' not in s:
    raise SystemExit("screen marker: EP44 marker not found")

path.write_text(s)
print("Applied Suicune Start Signature Probe v4.8")
