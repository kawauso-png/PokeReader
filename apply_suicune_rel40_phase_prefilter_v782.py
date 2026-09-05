from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v782 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# v7.8.2: conservative rel40 endpoint-phase impossibility filter.
#
# Exact-tail enumeration shows only 96/512 (base_hi, low6 carry-class)
# endpoint AP4 classes can produce any Gen-II shiny raw for any 16-bit
# predeep state under the validated route3+route4 deep profile union.
# rel40 does not yet know which stop branch will occur, so do NOT project one
# endpoint. Instead enumerate deliberately widened delta bands covering all
# observed cap_offset 728/729/730 macro branches. If every compatible endpoint
# class is mathematically non-shiny for every state/profile, abort at rel40.
# Otherwise fail open and retain the authoritative v7.8.1 DV-2 exact gate.
marker = '''// v7.8.1 endpoint exact-tail gate.\n'''
insert = r'''
// v7.8.2 rel40 endpoint-phase prefilter.
// Bit index = ((AP4 >> 6) & 0xff) * 2 + ((AP4 & 0x3f) >= 53).
// The 96 set bits were exhaustively derived from every initial ADD (0..255),
// both low-byte carry classes, all route3/route4 exact deep profiles, and the
// eight Gen-II shiny raws.  This test is existential over *all* predeep states:
// a clear bit means only "some state/profile can still be shiny".
const V782_SHINY_PHASE_BITS: [u8; 64] = [
    0x1f,0x00,0x00,0xfe,0x1f,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xfe,
    0x1f,0x00,0x00,0xfe,0x1f,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xfe,
    0x1f,0x00,0x00,0xfe,0x1f,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xfe,
    0x1f,0x00,0x00,0xfe,0x1f,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0xfe,
];

#[inline]
fn v782_endpoint_phase_can_shiny(ap4: u16) -> bool {
    let hi = ((ap4 >> 6) & 0xff) as usize;
    let carry_class = if (ap4 & 0x3f) >= 53 { 1usize } else { 0usize };
    let idx = hi * 2 + carry_class;
    (V782_SHINY_PHASE_BITS[idx >> 3] & (1u8 << (idx & 7))) != 0
}

#[inline]
fn v782_rel40_any_shiny_phase(rel40_ap4: u16) -> bool {
    // Observed rel40 -> DV-frame AP4 macro families, widened by +/-16 M-cycle
    // units around every measured family.  This intentionally trades rejection
    // rate for false-negative protection.  Historical compatible traces:
    // 47 checked, every actually shiny-capable endpoint phase passes.
    const RANGES: [(u16, u16); 4] = [
        (202, 236),
        (1371, 1416),
        (2544, 2579),
        (15413, 15450),
    ];
    let mut r = 0usize;
    while r < RANGES.len() {
        let (lo, hi) = RANGES[r];
        let mut d = lo;
        loop {
            let dv_ap4 = rel40_ap4.wrapping_add(d) & 0x3fff;
            if v782_endpoint_phase_can_shiny(dv_ap4) { return true; }
            if d == hi { break; }
            d = d.wrapping_add(1);
        }
        r += 1;
    }
    false
}

'''
if marker not in t:
    raise SystemExit('v782 insertion marker missing')
t = t.replace(marker, insert + marker, 1)

old_rel40 = '''                self.practical_post_proto=post.proto;self.practical_post_rot=post.rot40;self.practical_post_score=post.best_score;\n                // v7.6.4: live DivTracker indices can temporarily be unavailable after Exact2F.\n'''
new_rel40 = '''                self.practical_post_proto=post.proto;self.practical_post_rot=post.rot40;self.practical_post_score=post.best_score;\n\n                // v7.8.2 hard-negative phase prefilter.  This does not predict\n                // the final state and never selects one stop/route branch.  It\n                // asks only whether *any* conservatively compatible endpoint\n                // AP4 class can produce a shiny under any state/profile.\n                let rel40_ap4 = direct_phase_m((e.div >> 8) as u8, e.asub);\n                if !v782_rel40_any_shiny_phase(rel40_ap4) {\n                    self.practical_miss = 15;\n                    self.practical_terminal_advance = rng_advance();\n                    self.practical_active = false;\n                    self.probe_active = false;\n                    deep_log_stop();\n                    call_log_stop();\n                    self.state = TraceState::Done;\n                    self.save();\n                    pnp::request_pause();\n                    return;\n                }\n\n                // v7.6.4: live DivTracker indices can temporarily be unavailable after Exact2F.\n'''
t = rep(t, old_rel40, new_rel40, 'rel40 phase prefilter')

old_ui = '''            } else if self.practical_miss == 14 {\n                pnp::println!("TAIL NO SHINY");\n                pnp::println!("CAND {} SH{}",self.practical_support,self.practical_mask);\n            } else {\n'''
new_ui = '''            } else if self.practical_miss == 14 {\n                pnp::println!("TAIL NO SHINY");\n                pnp::println!("CAND {} SH{}",self.practical_support,self.practical_mask);\n            } else if self.practical_miss == 15 {\n                pnp::println!("REL40 PHASE NO SHINY");\n                pnp::println!("EARLY ABORT");\n            } else {\n'''
t = rep(t, old_ui, new_ui, 'rel40 phase UI')

t = t.replace('V781', 'V782', 1) if 'V781' in t else t
T.write_text(t)
print('Applied v7.8.2: conservative rel40 impossible-phase hard negative gate + v7.8.1 exact tail gate')
