#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
H = Path('reader_core/src/crystal/hook.rs')
t = T.read_text()
h = H.read_text()

def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v797 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

h = rep(h,
'''use super::reader::Gen2Reader;\nuse crate::{pnp, utils};\n''',
'''use super::reader::Gen2Reader;\nuse super::game_lib::gb_mem;\nuse crate::{pnp, utils};\n''', 'hook import gb_mem')

anchor = '''static mut PRE_VBLANK_TIMING_CAPTURE: bool = false;\nstatic mut PRE_VBLANK_TIMING_LAST_SLOT: u8 = 0xff;\n'''
insert = anchor + r'''

// v7.9.7 K-boundary blind probe. J's audio workload is deterministic; the
// remaining residual tracks the LCD/VBlank boundary. At the first rDIV read of
// each VBlank from rel18..45, capture the emulated SP and 12 guest stack bytes.
// In VBlank_Normal the interrupt return PC is expected at SP+10, but the raw
// bytes are retained so that assumption can be checked offline.
pub const V797_BOUNDARY_RING_LEN: usize = 32;
pub const V797_BOUNDARY_STACK_LEN: usize = 12;

#[derive(Clone, Copy)]
pub struct V797BoundaryRing {
    pub count: u8,
    pub write: u8,
    pub target: u32,
    pub advance: [u32; V797_BOUNDARY_RING_LEN],
    pub rel: [u8; V797_BOUNDARY_RING_LEN],
    pub sp: [u16; V797_BOUNDARY_RING_LEN],
    pub ret10: [u16; V797_BOUNDARY_RING_LEN],
    pub div: [u8; V797_BOUNDARY_RING_LEN],
    pub mcycle: [u8; V797_BOUNDARY_RING_LEN],
    pub stack: [[u8; V797_BOUNDARY_STACK_LEN]; V797_BOUNDARY_RING_LEN],
}
impl V797BoundaryRing {
    pub const EMPTY: Self = Self {
        count: 0, write: 0, target: 0,
        advance: [0; V797_BOUNDARY_RING_LEN],
        rel: [0; V797_BOUNDARY_RING_LEN],
        sp: [0; V797_BOUNDARY_RING_LEN],
        ret10: [0; V797_BOUNDARY_RING_LEN],
        div: [0; V797_BOUNDARY_RING_LEN],
        mcycle: [0; V797_BOUNDARY_RING_LEN],
        stack: [[0; V797_BOUNDARY_STACK_LEN]; V797_BOUNDARY_RING_LEN],
    };
}
static mut V797_BOUNDARY_RING: V797BoundaryRing = V797BoundaryRing::EMPTY;
static mut V797_BOUNDARY_CAPTURE: bool = false;
static mut V797_BOUNDARY_TARGET: u32 = 0;

pub fn v797_boundary_capture_start(target: u32) {
    unsafe {
        V797_BOUNDARY_RING = V797BoundaryRing::EMPTY;
        V797_BOUNDARY_RING.target = target;
        V797_BOUNDARY_TARGET = target;
        V797_BOUNDARY_CAPTURE = true;
    }
}
pub fn v797_boundary_capture_stop() {
    unsafe { V797_BOUNDARY_CAPTURE = false; }
}
pub fn latest_v797_boundary_ring() -> V797BoundaryRing {
    unsafe { V797_BOUNDARY_RING }
}

fn v797_boundary_capture_sample(advance: u32, div: u8, mcycle: u8) {
    unsafe {
        if !V797_BOUNDARY_CAPTURE { return; }
        let rel32 = advance.wrapping_sub(V797_BOUNDARY_TARGET);
        if rel32 > 45 {
            V797_BOUNDARY_CAPTURE = false;
            return;
        }
        if rel32 < 18 { return; }
        let i = V797_BOUNDARY_RING.write as usize;
        let sp = pnp::read::<u16>(CRYSTAL_CPU_CTX_BASE + 0x1e);
        let mut raw = [0u8; V797_BOUNDARY_STACK_LEN];
        for j in 0..V797_BOUNDARY_STACK_LEN {
            raw[j] = gb_mem::read_u8((sp as u32).wrapping_add(j as u32));
        }
        let ret10 = (raw[10] as u16) | ((raw[11] as u16) << 8);
        V797_BOUNDARY_RING.advance[i] = advance;
        V797_BOUNDARY_RING.rel[i] = rel32 as u8;
        V797_BOUNDARY_RING.sp[i] = sp;
        V797_BOUNDARY_RING.ret10[i] = ret10;
        V797_BOUNDARY_RING.div[i] = div;
        V797_BOUNDARY_RING.mcycle[i] = mcycle;
        V797_BOUNDARY_RING.stack[i] = raw;
        V797_BOUNDARY_RING.write = ((i + 1) % V797_BOUNDARY_RING_LEN) as u8;
        if (V797_BOUNDARY_RING.count as usize) < V797_BOUNDARY_RING_LEN {
            V797_BOUNDARY_RING.count += 1;
        }
    }
}
'''
h = rep(h, anchor, insert, 'boundary globals')

needle = '''        let div = reader.div();\n        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle, host_tick);\n\n        // Capture while the GB CPU is already stopped inside the rDIV hook.\n'''
insert2 = '''        let div = reader.div();\n        let post_advance = unsafe { RNG_ADVANCE.wrapping_add(1) };\n        push_pre_vblank_sample(post_advance, div, mcycle, host_tick);\n        v797_boundary_capture_sample(post_advance, div, mcycle);\n\n        // Capture while the GB CPU is already stopped inside the rDIV hook.\n'''
h = rep(h, needle, insert2, 'boundary hook sample')

needle = '''    PreVBlankRing, PreVBlankTimingRing, PRE_VBLANK_RING_LEN,\n};\n'''
insert3 = '''    PreVBlankRing, PreVBlankTimingRing, PRE_VBLANK_RING_LEN,\n    latest_v797_boundary_ring, v797_boundary_capture_start, v797_boundary_capture_stop,\n    V797_BOUNDARY_RING_LEN,\n};\n'''
t = rep(t, needle, insert3, 'trace imports')

needle = '''        self.probe_result = None;\n        self.probe_active = true;\n'''
insert4 = '''        self.probe_result = None;\n        v797_boundary_capture_start(self.probe_target.advance);\n        self.probe_active = true;\n'''
t = rep(t, needle, insert4, 'start boundary capture')

needle = '''            endpoint_fast_tail_stop();\n            self.probe_active = false;\n            self.state = TraceState::Done;\n'''
insert5 = '''            endpoint_fast_tail_stop();\n            v797_boundary_capture_stop();\n            self.probe_active = false;\n            self.state = TraceState::Done;\n'''
t = rep(t, needle, insert5, 'stop boundary capture')

old = '''                    if tail.shiny_count == 0 {\n                        // v7.8.1 hard negative gate: all currently validated\n                        // route3+route4 exact candidates are non-shiny. Save\n                        // this aborted trace and pause before any DV frame.\n                        self.practical_miss = 14;\n                        self.practical_terminal_advance = rng_advance();\n                        self.practical_active = false;\n                        self.probe_active = false;\n                        endpoint_fast_tail_stop();\n                        self.state = TraceState::Done;\n                        self.save();\n                        pnp::request_pause();\n                        return;\n                    }\n'''
new = '''                    if tail.shiny_count == 0 {\n                        // v7.9.7 blind-test override: preserve the hard-negative\n                        // telemetry (mask==0), but DO NOT abort at DV-2. Continue\n                        // through the game's native final Random/DV write so the\n                        // blind J prediction always receives final-DV ground truth.\n                        self.practical_terminal_advance = rng_advance();\n                    }\n'''
t = rep(t, old, new, 'disable DV-2 abort')

needle = '''        line.clear();\n        let _ = write!(line, "\\nstall_cpu_ctx,version,valid,target,pc,div,sub,bank,base,len,ctx_hex\\n");\n'''
insert6 = r'''        line.clear();
        let _ = write!(line, "\nk_boundary,version,index,target,advance,rel,sp,ret10,div,mcycle,stack12_hex\n");
        pnp::trace_file_write(line.as_bytes());
        let br = latest_v797_boundary_ring();
        let bn = (br.count as usize).min(V797_BOUNDARY_RING_LEN);
        let bstart = if bn == V797_BOUNDARY_RING_LEN { br.write as usize } else { 0 };
        for j in 0..bn {
            let i = (bstart + j) % V797_BOUNDARY_RING_LEN;
            line.clear();
            let _ = write!(line, "KBOUND,V797,{},{},{},{},{:04X},{:04X},{:02X},{:02X},",
                j, br.target, br.advance[i], br.rel[i], br.sp[i], br.ret10[i], br.div[i], br.mcycle[i]);
            for b in br.stack[i].iter() { let _ = write!(line, "{:02X}", *b); }
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _ = write!(line, "\nstall_cpu_ctx,version,valid,target,pc,div,sub,bank,base,len,ctx_hex\n");
'''
t = rep(t, needle, insert6, 'save boundary ring')

t = t.replace('STALLPHASE,V796,rel0-40+vblankirq+cpuctx84+audiopre+jpred-sd',
              'STALLPHASE,V797,rel0-40+vblankirq+cpuctx84+audiopre+jpred-sd+kbound', 1)

H.write_text(h)
T.write_text(t)
print('Applied v7.9.7 K-boundary blind probe + always-native-final-DV')
