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


# v6.2: lightweight rolling VBlank phase fingerprint.
# 17 samples => 16 deltas. Historical A/B/C/D prototype tables need only
# 12 exact consecutive deltas to distinguish all 4*16 ideal rotations, while
# 16 gives useful redundancy on hardware.
ring_block = r'''
pub const PRE_VBLANK_RING_LEN: usize = 17;

#[derive(Clone, Copy)]
pub struct PreVBlankRing {
    pub count: u8,
    pub write: u8,
    pub advance: [u32; PRE_VBLANK_RING_LEN],
    pub phase: [u16; PRE_VBLANK_RING_LEN],
}

impl PreVBlankRing {
    pub const EMPTY: Self = Self {
        count: 0,
        write: 0,
        advance: [0; PRE_VBLANK_RING_LEN],
        phase: [0; PRE_VBLANK_RING_LEN],
    };
}

static mut PRE_VBLANK_RING: PreVBlankRing = PreVBlankRing::EMPTY;

pub fn latest_pre_vblank_ring() -> PreVBlankRing {
    unsafe { PRE_VBLANK_RING }
}

fn push_pre_vblank_sample(advance: u32, div: u8, mcycle: u8) {
    unsafe {
        let idx = PRE_VBLANK_RING.write as usize;
        PRE_VBLANK_RING.advance[idx] = advance;
        PRE_VBLANK_RING.phase[idx] =
            (((div as u16) << 6) | ((mcycle as u16) & 0x3f)) & 0x3fff;
        PRE_VBLANK_RING.write =
            ((PRE_VBLANK_RING.write as usize + 1) % PRE_VBLANK_RING_LEN) as u8;
        if (PRE_VBLANK_RING.count as usize) < PRE_VBLANK_RING_LEN {
            PRE_VBLANK_RING.count += 1;
        }
    }
}
'''

anchor = '''pub fn set_vblank_context_capture(enabled: bool) {
    unsafe { VBLANK_CONTEXT_CAPTURE_ENABLED = enabled; }
}
'''
if "PRE_VBLANK_RING_LEN" not in h:
    h = rep(h, anchor, anchor + ring_block, "insert pre-vblank ring")

h = rep(
    h,
    '''    if RNG_DIV_READ_1.contains(&pc) {
        let div = reader.div();
''',
    '''    if RNG_DIV_READ_1.contains(&pc) {
        let div = reader.div();
        push_pre_vblank_sample(unsafe { RNG_ADVANCE.wrapping_add(1) }, div, mcycle);
''',
    "record pre-vblank ring",
)

# Import the lightweight snapshot into trace.rs after all previous generated
# hook imports have been applied.
if "latest_pre_vblank_ring" not in t:
    start = t.find("use super::hook::{")
    if start < 0:
        raise SystemExit("hook import block not found")
    end = t.find("};", start)
    if end < 0:
        raise SystemExit("hook import block end not found")
    t = (
        t[:end]
        + "    latest_pre_vblank_ring, PreVBlankRing, PRE_VBLANK_RING_LEN,\n"
        + t[end:]
    )

# v5.2 owns several frozen STARTSIG fields, and later generated patches add
# more fields around them. Match only the unique field line so v6.2 does not
# depend on adjacency to any specific previous patch.
t = rep(
    t,
    '''    startsig_vb_stack: [u32; 8],''',
    '''    startsig_vb_stack: [u32; 8],
    pre_vblank_ring: PreVBlankRing,''',
    "add trace pre-ring field",
)

t = rep(
    t,
    '''            startsig_vb_stack: [0; 8],''',
    '''            startsig_vb_stack: [0; 8],
            pre_vblank_ring: PreVBlankRing::EMPTY,''',
    "init trace pre-ring",
)

# Snapshot exactly at Y+X. Match only the stable capture-gate call; fields
# around it changed several times between v5.2 and v6.1c.
t = rep(
    t,
    '''        set_vblank_context_capture(false);''',
    '''        set_vblank_context_capture(false);
        self.pre_vblank_ring = latest_pre_vblank_ring();''',
    "snapshot pre-ring at Y+X",
)

helper = r'''
const PRE_FP_FRAME_M: i32 = 1172;
const PRE_FP_PROTOS: [[i16; 16]; 4] = [
    [1, -1, 0, -1, 2, -1, -8, 9, -1, -4, 5, -1, 0, -2, 3, -1],
    [-4, 7, -3, 0, -2, 3, -1, 2, 1, -3, 2, -1, -1, 3, 0, -3],
    [-2, 1, 1, -2, 2, 0, -1, 0, 1, -8, 7, 1, -4, 4, 0, 0],
    [2, 0, -2, 2, -1, -1, -8, 9, -1, -4, 5, -1, 0, -2, 3, -1],
];

fn pre_ring_start(r: &PreVBlankRing) -> usize {
    let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
    if count == PRE_VBLANK_RING_LEN {
        r.write as usize
    } else {
        0
    }
}

fn pre_ring_sample(r: &PreVBlankRing, chronological_index: usize) -> (u32, u16) {
    let start = pre_ring_start(r);
    let idx = (start + chronological_index) % PRE_VBLANK_RING_LEN;
    (r.advance[idx], r.phase[idx])
}

fn classify_pre_ring(r: &PreVBlankRing) -> (u8, u8, u16, u16, bool) {
    let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
    if count < 13 {
        return (b'?', 0, 0xffff, 0xffff, false);
    }

    let mut consecutive = true;
    for i in 1..count {
        let (pa, _) = pre_ring_sample(r, i - 1);
        let (ca, _) = pre_ring_sample(r, i);
        if ca != pa.wrapping_add(1) {
            consecutive = false;
        }
    }

    let delta_count = count - 1;
    let mut best_score = u32::MAX;
    let mut second_score = u32::MAX;
    let mut best_proto = 0usize;
    let mut best_rot = 0usize;

    for proto in 0..PRE_FP_PROTOS.len() {
        for rot in 0..16usize {
            let mut score = 0u32;
            for i in 0..delta_count {
                let (_, p0) = pre_ring_sample(r, i);
                let (_, p1) = pre_ring_sample(r, i + 1);
                let delta = ((p1 as i32 - p0 as i32) & 0x3fff) as i32;
                let observed = delta - PRE_FP_FRAME_M;
                let expected = PRE_FP_PROTOS[proto][(rot + i) & 15] as i32;
                let diff = observed - expected;
                score = score.saturating_add(if diff < 0 {
                    (-diff) as u32
                } else {
                    diff as u32
                });
            }
            if score < best_score {
                second_score = best_score;
                best_score = score;
                best_proto = proto;
                best_rot = rot;
            } else if score < second_score {
                second_score = score;
            }
        }
    }

    (
        b'A' + best_proto as u8,
        best_rot as u8,
        best_score.min(0xffff) as u16,
        second_score.min(0xffff) as u16,
        consecutive,
    )
}
'''
if "const PRE_FP_PROTOS" not in t:
    t = rep(
        t,
        '''fn direct_phase_m(div: u8, subtick: u8) -> u16 {
    (((div as u16) << 6) | subtick as u16) & 0x3fff
}
''',
        '''fn direct_phase_m(div: u8, subtick: u8) -> u16 {
    (((div as u16) << 6) | subtick as u16) & 0x3fff
}
''' + helper,
        "insert pre-ring classifier",
    )

# Raw phases/deltas are always saved even though a nearest historical
# prototype is also printed. That lets the offline model be changed later
# without asking for another hardware trace.
csv_block = r'''
        if self.probe_session {
            let r = self.pre_vblank_ring;
            let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
            let (proto, rot, best, second, consecutive) = classify_pre_ring(&r);
            let margin = second.saturating_sub(best);

            line.clear();
            let _ = write!(
                line,
                "\nprefingerprint,version,count,consecutive,proto,pre_rot,best_score,second_score,margin,first_advance,last_advance"
            );
            for i in 0..PRE_VBLANK_RING_LEN {
                let _ = write!(line, ",p{}", i);
            }
            for i in 0..(PRE_VBLANK_RING_LEN - 1) {
                let _ = write!(line, ",d{}", i);
            }
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());

            line.clear();
            let first_advance = if count > 0 {
                pre_ring_sample(&r, 0).0
            } else {
                0
            };
            let last_advance = if count > 0 {
                pre_ring_sample(&r, count - 1).0
            } else {
                0
            };
            let _ = write!(
                line,
                "PREFP,V62,{},{},{},{},{},{},{},{},{}",
                count,
                consecutive as u8,
                proto as char,
                rot,
                best,
                second,
                margin,
                first_advance,
                last_advance
            );
            for i in 0..PRE_VBLANK_RING_LEN {
                if i < count {
                    let (_, phase) = pre_ring_sample(&r, i);
                    let _ = write!(line, ",{:04X}", phase);
                } else {
                    let _ = write!(line, ",");
                }
            }
            for i in 0..(PRE_VBLANK_RING_LEN - 1) {
                if i + 1 < count {
                    let (_, p0) = pre_ring_sample(&r, i);
                    let (_, p1) = pre_ring_sample(&r, i + 1);
                    let delta = ((p1 as i32 - p0 as i32) & 0x3fff) - PRE_FP_FRAME_M;
                    let _ = write!(line, ",{}", delta);
                } else {
                    let _ = write!(line, ",");
                }
            }
            let _ = write!(line, "\n\n");
            pnp::trace_file_write(line.as_bytes());
        }

'''

frame_anchor = '''        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"
        );'''
if "PREFP,V62" not in t:
    t = rep(t, frame_anchor, csv_block + frame_anchor, "write PREFP row")

hook_path.write_text(h)
trace_path.write_text(t)
print("Applied Suicune Pre-Fingerprint v6.2")
