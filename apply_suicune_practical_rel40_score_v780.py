from pathlib import Path

P = Path('reader_core/src/crystal/practical.rs')
T = Path('reader_core/src/crystal/trace.rs')

p = P.read_text()
t = T.read_text()

MARK = '// v7.8.0 PRACTICAL REL40 MODAL SCORE'
if MARK in p or 'REL40SCORE,V780' in t:
    raise SystemExit('v780 already applied')

helper = r'''

// v7.8.0 PRACTICAL REL40 MODAL SCORE
// Observation-only bridge-validation build.  The score starts from ACTUAL
// rel40 because PRE->rel40 was not stable enough in the i/j corpus to justify
// a pre-input shiny claim.  The canonical tail is only a coordinate system:
// rows122/G581, persistent -5645 AP4 shift from rel717, route3 P0/P0 deep.
// No game memory, RNG, DIV, DV, save, or input is written here.
#[derive(Clone, Copy, Default)]
pub struct V780Rel40Score {
    pub score: u8,
    pub cell_n: u8,
    pub mode_count: u8,
    pub canonical_raw: u16,
    pub predicted_raw: u16,
    pub residual_hi: u8,
    pub residual_lo: u8,
}

#[inline]
fn v780_step(state: u16, ap4: u16) -> u16 {
    let add = (state >> 8) as u8;
    let sub = state as u8;
    let hi = ((ap4 >> 6) & 0xff) as u8;
    let lo = (((ap4.wrapping_add(11)) >> 6) & 0xff) as u8;
    let z = add as u16 + hi as u16;
    let carry = if z > 0xff { 1u8 } else { 0u8 };
    let na = z as u8;
    let ns = sub.wrapping_sub(lo).wrapping_sub(carry);
    ((na as u16) << 8) | ns as u16
}

#[inline]
fn v780_is_shiny(raw: u16) -> bool {
    matches!(raw, 0x2aaa | 0x3aaa | 0x6aaa | 0x7aaa |
                  0xaaaa | 0xbaaa | 0xeaaa | 0xfaaa)
}

fn v780_canonical_raw(state40: u16, ap40: u16) -> u16 {
    const MOD: u32 = 16384;
    const FRAME_M: u32 = 1172;
    const SHIFT_122: u32 = 5645;
    const P0: [u8; 3] = [183, 189, 191];

    let mut st = state40;
    let mut last_ap = ap40 & 0x3fff;
    let mut rel = 41u32;
    while rel <= 729 {
        let d = (FRAME_M * (rel - 40)) % MOD;
        let mut ap = ((ap40 as u32 + d) % MOD) as u16;
        if rel >= 717 {
            ap = ((ap as u32 + MOD - SHIFT_122) % MOD) as u16;
        }
        st = v780_step(st, ap);
        last_ap = ap;
        rel += 1;
    }

    let la = ((last_ap >> 6) & 0xff) as u8;
    let ls = (((last_ap.wrapping_add(11)) >> 6) & 0xff) as u8;
    let mut hi_raw = 0u8;
    let mut lo_raw = 0u8;
    for i in 0..3usize {
        let a = la.wrapping_add(P0[i]);
        let s = ls.wrapping_add(P0[i]);
        let add = (st >> 8) as u8;
        let sub = st as u8;
        let z = add as u16 + a as u16;
        let carry = if z > 0xff { 1u8 } else { 0u8 };
        let na = z as u8;
        let ns = sub.wrapping_sub(s).wrapping_sub(carry);
        st = ((na as u16) << 8) | ns as u16;
        if i == 1 { hi_raw = ns; }
        if i == 2 { lo_raw = ns; }
    }
    ((hi_raw as u16) << 8) | lo_raw as u16
}

pub fn evaluate_rel40_mode_v780(proto: u8, rot: u8, state40: u16, ap40: u16) -> V780Rel40Score {
    let canonical = v780_canonical_raw(state40, ap40);

    // Repeated modes only; singleton residuals are intentionally excluded.
    // i/j Pause45 source counts:
    // A/r2 (+4,+4) 2/7; B/r9 (-2,-2) 2/4;
    // C/r2 (-35,-35) 2/7; D/r2 (-2,-2) 4/7.
    let (rh, rl, n, count, empirical_score) = match (proto, rot) {
        (b'A', 2) => (4u8,   4u8,   7u8, 2u8, 29u8),
        (b'B', 9) => (254u8, 254u8, 4u8, 2u8, 50u8),
        (b'C', 2) => (221u8, 221u8, 7u8, 2u8, 29u8),
        (b'D', 2) => (254u8, 254u8, 7u8, 4u8, 57u8),
        _ => return V780Rel40Score { canonical_raw: canonical, ..V780Rel40Score::default() },
    };

    let ph = (canonical >> 8) as u8;
    let pl = canonical as u8;
    let predicted = ((ph.wrapping_add(rh) as u16) << 8) |
                    pl.wrapping_add(rl) as u16;
    let score = if v780_is_shiny(predicted) { empirical_score } else { 0 };
    V780Rel40Score {
        score,
        cell_n: n,
        mode_count: count,
        canonical_raw: canonical,
        predicted_raw: predicted,
        residual_hi: rh,
        residual_lo: rl,
    }
}
'''
p += helper
P.write_text(p)

old_gate = '''                // v7.6.6 ends every diagnostic run at rel40 after recording the
                // actual POST/J/state/div and suffix-gate support.  This avoids a
                // 700-frame tail and makes each M replicate fast and comparable.
                self.practical_fail(13);return
'''
new_gate = '''                // v7.8.0 EXP: score ACTUAL rel40 but never gate this validation
                // run.  Every k run reaches the native final DV so PRE->rel40 and
                // rel40->DV can both be measured without selection bias.
                let ap40=direct_phase_m(((e.div>>8)&0xff) as u8,e.asub);
                let q=practical::evaluate_rel40_mode_v780(post.proto,post.rot40,e.state,ap40);
                self.practical_support=q.score;
                self.practical_raw=q.predicted_raw;
                self.practical_mask=q.mode_count;
                self.practical_active=false;
                self.practical_candidate_valid=false;
                self.bucket_model_active=false;
                self.practical_miss=0;
                return
'''
if t.count(old_gate) != 1:
    raise SystemExit(f'v780 rel40 gate anchor count {t.count(old_gate)}')
t = t.replace(old_gate, new_gate, 1)

close = '        pnp::trace_file_close();\n'
pos = t.rfind(close)
if pos < 0:
    raise SystemExit('v780 final trace close not found')
telemetry = '''        line.clear();
        let _=write!(line,"\\nrel40_score,version,post_proto,post_rot,score,mode_count,pred_raw,decision,miss\\nREL40SCORE,V780,{},{},{},{},{:04X},{},{}\\n",
            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},
            self.practical_post_rot,self.practical_support,self.practical_mask,self.practical_raw,
            if self.practical_support>=20{"HIGH"}else{"OBSERVE"},self.practical_miss);
        pnp::trace_file_write(line.as_bytes());

'''
t = t[:pos] + telemetry + t[pos:]
T.write_text(t)

print('Applied v7.8.0 observation-only rel40 modal score probe')
