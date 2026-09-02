#!/usr/bin/env python3
from pathlib import Path

# v7.2.0 is applied after a long historical patch chain.  Whitespace around
# PREFP has changed several times, so do not mutate generated Rust to fit a
# brittle multiline Python string.  Instead, rewrite the v7.2 apply script's
# CSV insertion step to splice immediately before one semantic marker that is
# unique in the final v7.1.9 source.
p = Path('apply_suicune_branchphase_probe_v720.py')
s = p.read_text()

start_marker = '# CSV: compute AA/AB deltas offline from the frozen timing snapshot.'
end_marker = '# Dedicated diagnostic UI. The physical UP+B/Exact2F execution path is unchanged.'
start = s.find(start_marker)
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('v720 normalizer: CSV source section markers missing')

replacement = r'''# CSV: compute AA/AB deltas offline from the frozen timing snapshot.  Insert by
# semantic marker rather than matching PREFP whitespace.  Recreate r/count in
# this independent block because the preceding PREFP block has already closed.
marker = '        // v6.3 authoritative suffix fingerprint.'
if t.count(marker) != 1:
    raise SystemExit(f'v720 BRPHASE semantic marker: expected 1 match, got {t.count(marker)}')
phase_block = r'''        if self.probe_session {
            let r = self.pre_vblank_ring;
            let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
            let tr = self.pre_vblank_timing_ring;
            let tc = (tr.count as usize).min(PRE_VBLANK_RING_LEN);
            let ts = if tc == PRE_VBLANK_RING_LEN { tr.write as usize } else { 0 };
            line.clear();
            let _ = write!(line, "branch_phase,version,index,advance,phase,a_tick,b_tick,aa_delta,ab_delta\n");
            pnp::trace_file_write(line.as_bytes());
            let mut prev_a = 0u64;
            for i in 0..count.min(tc) {
                let (adv, phase) = pre_ring_sample(&r, i);
                let ti = (ts + i) % PRE_VBLANK_RING_LEN;
                let a = tr.a_tick[ti];
                let b = tr.b_tick[ti];
                let aa = if prev_a != 0 { a.saturating_sub(prev_a) } else { 0 };
                let ab = if b >= a { b - a } else { 0 };
                prev_a = a;
                line.clear();
                let _ = write!(line, "BRPHASE,V720,{},{},{:04X},{},{},{},{}\n", i, adv, phase, a, b, aa, ab);
                pnp::trace_file_write(line.as_bytes());
            }
            line.clear();
            let _ = write!(line, "\n");
            pnp::trace_file_write(line.as_bytes());
        }

'''
pos = t.find(marker)
t = t[:pos] + phase_block + t[pos:]

'''

s = s[:start] + replacement + s[end:]
p.write_text(s)
print('Normalized v7.2 apply script: BRPHASE now splices at semantic POSTFP marker')
