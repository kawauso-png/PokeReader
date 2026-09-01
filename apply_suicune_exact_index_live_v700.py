#!/usr/bin/env python3
from pathlib import Path
import ast, base64, zlib

TRACE = Path('reader_core/src/crystal/trace.rs')
PRACTICAL = Path('reader_core/src/crystal/practical.rs')
PAYLOADS = [Path('apply_suicune_practical_shiny_v64_payload_0.txt'), Path('apply_suicune_practical_shiny_v64_payload_1.txt')]

SOURCE_INDEX = {
    87: (1866, 1153),
    94: (1023, 310),
    95: (9878, 9165),
    89: (3484, 10278),
    96: (2269, 9063),
    86: (10679, 1089),
}

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)

def decode_lanes():
    payload = ''.join(p.read_text().strip() for p in PAYLOADS).encode('ascii')
    decoded = zlib.decompress(base64.b85decode(payload)).decode('utf-8')
    tree = ast.parse(decoded)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'LANES' for t in node.targets):
            return ast.literal_eval(node.value)
    raise SystemExit('LANES not found in v6.4 generator payload')

def rust_u8_array(name, vals):
    lines = []
    for i in range(0, len(vals), 24):
        lines.append('    ' + ', '.join(str(v) for v in vals[i:i+24]) + ',')
    return f'const {name}: [u8; 730] = [\n' + '\n'.join(lines) + '\n];\n'

lanes = decode_lanes()
if len(lanes) != 6:
    raise SystemExit(f'expected 6 lanes, got {len(lanes)}')

p = PRACTICAL.read_text()
p = replace_once(
    p,
    '    last_a: u8, last_s: u8,\n',
    '''    last_a: u8, last_s: u8,
    raw_a: &'static [u8; 730],
    raw_s: &'static [u8; 730],
    source_ai: u32,
    source_si: u32,
''',
    'Lane exact-index fields',
)

for lane_id, source, _proto, _rot, ahex, shex in lanes:
    oa = list(bytes.fromhex(ahex))
    os = list(bytes.fromhex(shex))
    if len(oa) != 730 or len(os) != 730:
        raise SystemExit(f'lane {lane_id}: expected 730 offsets')
    ai, si = SOURCE_INDEX[source]
    marker = f'const L{lane_id}: Lane = Lane {{\n'
    arrays = rust_u8_array(f'L{lane_id}_RAW_A', oa) + rust_u8_array(f'L{lane_id}_RAW_S', os) + '\n'
    p = replace_once(p, marker, arrays + marker, f'lane {lane_id} raw arrays')
    start = p.index(marker)
    end = p.index('\n};', start)
    block = p[start:end]
    line_end = block.index('\n', block.index('    post_rot:')) + 1
    inject = f'''    raw_a: &L{lane_id}_RAW_A,
    raw_s: &L{lane_id}_RAW_S,
    source_ai: {ai},
    source_si: {si},
'''
    block = block[:line_end] + inject + block[line_end:]
    p = p[:start] + block + p[end:]

start_marker = '// v6.9.0: measured full-index cadence exceptions.'
end_marker = 'pub const SEARCH_HORIZON: u32 = 12000;'
start = p.find(start_marker)
end = p.find(end_marker)
if start < 0 or end < 0 or end <= start:
    raise SystemExit('v6.9 exact-index replacement span not found')

exact_code = r'''// v7.0 Exact-Index LiveRoot.
// The empirical lane paths were measured at specific absolute DivTracker
// indices. Remove the donor exception contribution, then apply the current
// root contribution. Source==target therefore reproduces the donor exactly.
fn cadence_correction(index: u32) -> i16 {
    normal_inc_full(index) as i16 - normal_inc(index) as i16
}
fn corrected_offset(raw: u8, target_corr: i16, source_corr: i16) -> u8 {
    raw.wrapping_add(target_corr.wrapping_sub(source_corr) as u8)
}
fn deep_prediction(id: u8, l: &Lane, predeep: u16, last_a: u8, last_s: u8,
    e40_state: u16, e40_div: u16, e716_state: u16, e716_div: u16,
    e717_state: u16, e717_div: u16) -> Option<Prediction> {
    let mut support = 0u8; let mut mask = 0u8; let mut first_raw = 0u16;
    for i in 0..5usize {
        let mut st = predeep; let mut lows = [0u8; 3];
        for j in 0..3usize {
            st = upd(st, last_a.wrapping_add(DEEP_A[i][j]), last_s.wrapping_add(DEEP_S[i][j]));
            lows[j] = st as u8;
        }
        if lows[0] >= 0xc0 { continue; }
        let raw = ((lows[1] as u16) << 8) | lows[2] as u16;
        if shiny(raw) {
            support = support.saturating_add(DEEP_WEIGHT[i]); mask |= 1u8 << i;
            if first_raw == 0 { first_raw = raw; }
        }
    }
    if support < MIN_SUPPORT_WEIGHT { return None; }
    Some(Prediction { lane_id: id, source: l.source, support_weight: support,
        shiny_mask: mask, raw: first_raw, expected40_state: e40_state,
        expected40_div: e40_div, expected716_state: e716_state,
        expected716_div: e716_div, expected717_state: e717_state,
        expected717_div: e717_div })
}
pub fn evaluate_exact(id: u8, state: u16, div: u16, ai: u32, si: u32) -> Option<Prediction> {
    let l = lane(id); let av0 = (div >> 8) as u8; let sv0 = div as u8; let mut st = state;
    let mut tca=0i16; let mut tcs=0i16; let mut sca=0i16; let mut scs=0i16;
    let mut e40s=0u16; let mut e40d=0u16; let mut e716s=0u16; let mut e716d=0u16;
    let mut e717s=0u16; let mut e717d=0u16; let mut last_a=0u8; let mut last_s=0u8;
    for rel in 0..730usize {
        let r=rel as u32;
        tca += cadence_correction(ai.wrapping_add(r) & 0x3fff);
        tcs += cadence_correction(si.wrapping_add(r) & 0x3fff);
        sca += cadence_correction(l.source_ai.wrapping_add(r) & 0x3fff);
        scs += cadence_correction(l.source_si.wrapping_add(r) & 0x3fff);
        let a=av0.wrapping_add(corrected_offset(l.raw_a[rel],tca,sca));
        let s=sv0.wrapping_add(corrected_offset(l.raw_s[rel],tcs,scs));
        st=upd(st,a,s);
        if rel==40 { e40s=st; e40d=((a as u16)<<8)|s as u16; }
        else if rel==716 { e716s=st; e716d=((a as u16)<<8)|s as u16; }
        else if rel==717 { e717s=st; e717d=((a as u16)<<8)|s as u16; }
        if rel==729 { last_a=a; last_s=s; }
    }
    deep_prediction(id,l,st,last_a,last_s,e40s,e40d,e716s,e716d,e717s,e717d)
}
pub fn lane_for_post_unique(proto: u8, rot: u8) -> Option<u8> {
    let mut found=0u8; let mut count=0u8;
    for id in 1..=LANE_COUNT { let l=lane(id); if l.post_proto==proto && l.post_rot==rot {
        found=id; count=count.saturating_add(1); } }
    if count==1 { Some(found) } else { None }
}
pub fn evaluate_post_exact(id: u8, state40: u16, div40: u16, ai40: u32, si40: u32) -> Option<Prediction> {
    let l=lane(id); let av40=(div40>>8) as u8; let sv40=div40 as u8;
    let raw40a=l.raw_a[40]; let raw40s=l.raw_s[40];
    let sai40=l.source_ai.wrapping_add(41)&0x3fff; let ssi40=l.source_si.wrapping_add(41)&0x3fff;
    let mut tca=0i16; let mut tcs=0i16; let mut sca=0i16; let mut scs=0i16; let mut st=state40;
    let mut e716s=0u16; let mut e716d=0u16; let mut e717s=0u16; let mut e717d=0u16;
    let mut last_a=0u8; let mut last_s=0u8;
    for rel in 41..730usize {
        let step=(rel-41) as u32;
        tca += cadence_correction(ai40.wrapping_add(step)&0x3fff);
        tcs += cadence_correction(si40.wrapping_add(step)&0x3fff);
        sca += cadence_correction(sai40.wrapping_add(step)&0x3fff);
        scs += cadence_correction(ssi40.wrapping_add(step)&0x3fff);
        let ra=l.raw_a[rel].wrapping_sub(raw40a); let rs=l.raw_s[rel].wrapping_sub(raw40s);
        let a=av40.wrapping_add(corrected_offset(ra,tca,sca));
        let s=sv40.wrapping_add(corrected_offset(rs,tcs,scs));
        st=upd(st,a,s);
        if rel==716 { e716s=st; e716d=((a as u16)<<8)|s as u16; }
        else if rel==717 { e717s=st; e717d=((a as u16)<<8)|s as u16; }
        if rel==729 { last_a=a; last_s=s; }
    }
    deep_prediction(id,l,st,last_a,last_s,state40,div40,e716s,e716d,e717s,e717d)
}

'''
p = p[:start] + exact_code + p[end:]
PRACTICAL.write_text(p)

t = TRACE.read_text()
t = replace_once(t,'    practical_live_index_reject: u32,\n','''    practical_live_index_wait: u32,
    practical_live_exact_eval: u32,
''','v700 runtime fields')
t = replace_once(t,'            practical_live_index_reject: 0,\n','''            practical_live_index_wait: 0,
            practical_live_exact_eval: 0,
''','v700 runtime defaults')
t = replace_once(t,'        self.practical_live_index_reject = 0;\n','''        self.practical_live_index_wait = 0;
        self.practical_live_exact_eval = 0;
''','v700 scan reset')
old_monitor='''        let state = reader.rng_state();
        let div = measured_div();
        let Some(p) = practical::evaluate(lane_id, state, div) else {
            return;
        };

        let ai = (add_div_tracker().index().unwrap_or(0) as u32) & 0x3fff;
        let si = (sub_div_tracker().index().unwrap_or(0) as u32) & 0x3fff;
        if !practical::full_index_window_safe(ai, si) {
            self.practical_live_index_reject = self.practical_live_index_reject.saturating_add(1);
            return;
        }
'''
new_monitor='''        let Some(ai_raw) = add_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let Some(si_raw) = sub_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let ai = (ai_raw as u32) & 0x3fff;
        let si = (si_raw as u32) & 0x3fff;
        let state = reader.rng_state();
        let div = measured_div();
        self.practical_live_exact_eval = self.practical_live_exact_eval.saturating_add(1);
        let Some(p) = practical::evaluate_exact(lane_id, state, div, ai, si) else {
            return;
        };
'''
t=replace_once(t,old_monitor,new_monitor,'exact live monitor')
old_rebind='''                        if let Some(post_lane) = practical::lane_for_post_unique(post.proto, post.rot40) {
                            if let Some(pred) = practical::evaluate_post_unique(post_lane, e.state, e.div) {
                                self.rebind_practical_post_v690(pred, post.proto, post.rot40);
                            } else {
                                self.practical_fail(1);
                                return;
                            }
                        } else {
'''
new_rebind='''                        if let Some(post_lane) = practical::lane_for_post_unique(post.proto, post.rot40) {
                            let Some(ai40_raw) = add_div_tracker().index() else { self.practical_fail(1); return; };
                            let Some(si40_raw) = sub_div_tracker().index() else { self.practical_fail(1); return; };
                            if let Some(pred) = practical::evaluate_post_exact(post_lane,e.state,e.div,
                                (ai40_raw as u32)&0x3fff,(si40_raw as u32)&0x3fff) {
                                self.rebind_practical_post_v690(pred, post.proto, post.rot40);
                            } else { self.practical_fail(1); return; }
                        } else {
'''
t=replace_once(t,old_rebind,new_rebind,'exact rel40 rebind')
old_csv='''                "BRANCH690,V690,{},{:02X},{},{},{},{},{},{}\\n",
                (self.practical_post_proto != 0) as u8,
                self.practical_post_proto,
                self.practical_post_rot,
                self.practical_post_score,
                self.practical_rebound as u8,
                self.practical_live_index_reject,
                self.practical_live_found_ai,
                self.practical_live_found_si
'''
new_csv='''                "BRANCH700,V700,{},{:02X},{},{},{},{},{},{},{}\\n",
                (self.practical_post_proto != 0) as u8,
                self.practical_post_proto,
                self.practical_post_rot,
                self.practical_post_score,
                self.practical_rebound as u8,
                self.practical_live_index_wait,
                self.practical_live_exact_eval,
                self.practical_live_found_ai,
                self.practical_live_found_si
'''
t=replace_once(t,old_csv,new_csv,'v700 telemetry')
old_scan='''                    "S690 SCAN A{} C{} L{} X{}",
                    rng_advance().wrapping_sub(self.practical_live_start_advance),
                    self.practical_live_checked,
                    self.practical_live_lane_frames,
                    self.practical_live_index_reject
'''
new_scan='''                    "S700 SCAN A{} C{} L{} I{} E{}",
                    rng_advance().wrapping_sub(self.practical_live_start_advance),
                    self.practical_live_checked,
                    self.practical_live_lane_frames,
                    self.practical_live_index_wait,
                    self.practical_live_exact_eval
'''
t=replace_once(t,old_scan,new_scan,'v700 scan UI')
t=t.replace('S690 ','S700 ')
TRACE.write_text(t)

p2=PRACTICAL.read_text(); t2=TRACE.read_text()
for x in ['pub fn evaluate_exact','pub fn evaluate_post_exact','source_ai:','raw_a:','cadence_correction']:
    if x not in p2: raise SystemExit(f'missing practical marker {x}')
for x in ['S700 SCAN','BRANCH700,V700','practical_live_index_wait','practical_live_exact_eval','evaluate_exact(lane_id']:
    if x not in t2: raise SystemExit(f'missing trace marker {x}')
if old_monitor in t2: raise SystemExit('v6.9 monitor with unwrap_or(0) still active')
if 'full_index_window_safe(ai, si)' in t2: raise SystemExit('v6.9 candidate rejection still active')
if 'evaluate_post_unique(post_lane' in t2: raise SystemExit('nominal POST rebind still active')
if 'S658 TEST' not in t2: raise SystemExit('FastValidate S658 lost')
print('Applied Suicune v7.0 Exact-Index LiveRoot: donor-normalized full-index evaluator, explicit IDX WAIT, exact POST suffix')
