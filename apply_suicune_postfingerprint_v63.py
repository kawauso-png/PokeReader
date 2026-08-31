#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
s = path.read_text()


def rep(old: str, new: str, label: str) -> None:
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    s = s.replace(old, new, 1)


# v6.3 is deliberately small:
#   * classify the post-stop1 16-cycle cell from rel28..40 (12 deltas),
#   * save the raw 13 phases + 12 deltas for offline reclassification,
#   * do not pause at the late DV-2 Endpoint. PURETAIL is already active there,
#     so the final two advances can run cleanly without a human R press.
#
# 0095 proved that the PRE fingerprint remains exact through stop1 entry, but
# the stop1 transition can change prototype/rotation. Therefore PRE is kept as
# diagnostic context while POST becomes the authoritative suffix classifier.

post_helper = r'''
#[derive(Clone, Copy)]
struct PostFingerprint {
    valid: bool,
    proto: u8,
    rot40: u8,
    best_score: u16,
    second_score: u16,
    phases: [u16; 13],
    deltas: [i16; 12],
}

impl PostFingerprint {
    const EMPTY: Self = Self {
        valid: false,
        proto: b'?',
        rot40: 0,
        best_score: 0xffff,
        second_score: 0xffff,
        phases: [0; 13],
        deltas: [0; 12],
    };
}

fn post_phase_at_rel(
    entries: &[TraceEntry],
    len: usize,
    target_advance: u32,
    rel: u32,
) -> Option<u16> {
    // CSV rel_adv 0 is the first running frame, i.e. Target+1.
    let wanted = target_advance.wrapping_add(rel).wrapping_add(1);
    for e in entries.iter().take(len) {
        if e.advance == wanted {
            return Some(direct_phase_m((e.div >> 8) as u8, e.asub));
        }
    }
    None
}

fn classify_post_entries(entries: &[TraceEntry], len: usize, target_advance: u32) -> PostFingerprint {
    let mut out = PostFingerprint::EMPTY;

    // 13 phases rel28..40 give exactly 12 consecutive deltas. Across the
    // historical A/B/C/D prototypes, 12 deltas uniquely distinguish all
    // 4 * 16 rotations. rel28 is used because 0095 is already on the clean
    // post-stop1 backbone there, leaving ~177 advances before the first large
    // local structural window around rel217.
    for i in 0..13usize {
        let Some(p) = post_phase_at_rel(entries, len, target_advance, 28 + i as u32) else {
            return out;
        };
        out.phases[i] = p;
    }

    for i in 0..12usize {
        let delta = ((out.phases[i + 1] as i32 - out.phases[i] as i32) & 0x3fff)
            - PRE_FP_FRAME_M;
        out.deltas[i] = delta as i16;
    }

    let mut best_score = u32::MAX;
    let mut second_score = u32::MAX;
    let mut best_proto = 0usize;
    let mut best_rot28 = 0usize;

    for proto in 0..PRE_FP_PROTOS.len() {
        for rot28 in 0..16usize {
            let mut score = 0u32;
            for i in 0..12usize {
                let observed = out.deltas[i] as i32;
                let expected = PRE_FP_PROTOS[proto][(rot28 + i) & 15] as i32;
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
                best_rot28 = rot28;
            } else if score < second_score {
                second_score = score;
            }
        }
    }

    out.valid = true;
    out.proto = b'A' + best_proto as u8;
    // Canonical rotation is reported at rel40, matching the old rel40..55
    // classifier and existing Factor/Prototype notes.
    out.rot40 = ((best_rot28 + 12) & 15) as u8;
    out.best_score = best_score.min(0xffff) as u16;
    out.second_score = second_score.min(0xffff) as u16;
    out
}

'''

anchor = '''/// Small stack formatter so a CSV row can be built without allocating.'''
if "struct PostFingerprint" not in s:
    rep(anchor, post_helper + anchor, "insert POST fingerprint classifier")

post_csv = r'''
        // v6.3 authoritative suffix fingerprint. line.clear() here also fixes
        // the v6.2 duplicate PREFP row caused by the following frame header
        // being appended to the still-populated line buffer.
        line.clear();
        if self.probe_session {
            let post = classify_post_entries(self.entries, self.len, self.probe_target.advance);
            let margin = post.second_score.saturating_sub(post.best_score);
            let _ = write!(
                line,
                "postfingerprint,version,valid,proto,post_rot,best_score,second_score,margin"
            );
            for i in 0..13usize {
                let _ = write!(line, ",p{}", 28 + i);
            }
            for i in 0..12usize {
                let _ = write!(line, ",d{}", 28 + i);
            }
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());
            line.clear();

            let _ = write!(
                line,
                "POSTFP,V63,{},{},{},{},{},{}",
                post.valid as u8,
                post.proto as char,
                post.rot40,
                post.best_score,
                post.second_score,
                margin
            );
            for i in 0..13usize {
                if post.valid {
                    let _ = write!(line, ",{:04X}", post.phases[i]);
                } else {
                    let _ = write!(line, ",");
                }
            }
            for i in 0..12usize {
                if post.valid {
                    let _ = write!(line, ",{}", post.deltas[i]);
                } else {
                    let _ = write!(line, ",");
                }
            }
            let _ = write!(line, "\n\n");
            pnp::trace_file_write(line.as_bytes());
            line.clear();
        }

'''

frame_anchor = '''        let _ = write!(
            line,
            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"
        );'''
if "POSTFP,V63" not in s:
    rep(frame_anchor, post_csv + frame_anchor, "write POST fingerprint row")

# Endpoint v4.4 already switches Random rDIV hooks to PURETAIL before the
# DV-generation burst. The late pause was useful for calibration but now only
# forces a human R input at rel728 and marks clean_tail=0. Let the two remaining
# advances run immediately; result locking will restore normal hooks.
rep(
    '''                endpoint_fast_tail_start();
                pnp::request_pause();''',
    '''                endpoint_fast_tail_start();
                // v6.3: no late DV-2 pause. Keep the tail input-free and let
                // the existing result detector/auto-save finish naturally.''',
    "remove late endpoint pause",
)

path.write_text(s)
print("Applied Suicune Post-Fingerprint v6.3")
