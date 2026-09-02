#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/practical.rs')
T = Path('reader_core/src/crystal/trace.rs')
M = Path('3gx/sources/main.c')
p = P.read_text()
t = T.read_text()
m = M.read_text()

TARGET_BUCKET = 76
TARGET_POST_PROTO = 'C'
TARGET_POST_ROT = 8


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v734 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


def fspan(src, sig):
    a = src.find(sig)
    if a < 0:
        raise SystemExit(f'v734 missing function {sig}')
    b = src.find('{', a)
    if b < 0:
        raise SystemExit(f'v734 missing opening brace {sig}')
    d = 0
    for i in range(b, len(src)):
        if src[i] == '{':
            d += 1
        elif src[i] == '}':
            d -= 1
            if d == 0:
                e = i + 1
                while e < len(src) and src[e] in ' \t':
                    e += 1
                if e < len(src) and src[e] == '\n':
                    e += 1
                return a, e
    raise SystemExit(f'v734 unclosed function {sig}')

# -------------------------------------------------------------------------
# 1) Branch-resolved empirical evaluator.
#    v7.1's evaluate_empirical() selects the first donor matching PRE only.
#    A/r10 is now known to be one-to-many, so v7.3.4 explicitly selects the
#    registered A/r10 -> C/r8 donor when bucket 76 is observed.
# -------------------------------------------------------------------------
anchor = "pub fn evaluate_empirical(proto:u8,rot:u8,state:u16,div:u16,ai:u32,si:u32)->Option<Prediction>{"
if anchor not in p:
    raise SystemExit('v734 empirical evaluator anchor missing')

helper = r'''
fn emp_pre_post(p:u8,r:u8,op:u8,orr:u8)->Option<&'static EmpLane>{
    EMP_LANES.iter().find(|x|
        x.pre_proto==p && x.pre_rot==r && x.post_proto==op && x.post_rot==orr)
}

/// Branch-resolved empirical prediction used by v7.3.4 PhaseBucket Shiny Probe.
/// Returns Some only when the selected donor predicts a Gen2 shiny DV.
pub fn evaluate_empirical_post(
    proto:u8,rot:u8,post_proto:u8,post_rot:u8,
    state:u16,div:u16,ai:u32,si:u32
)->Option<Prediction>{
    if !empirical_window_safe(ai,si){return None}
    let l=emp_pre_post(proto,rot,post_proto,post_rot)?;
    let av=(div>>8)as u8;
    let sv=div as u8;
    let pre=apply_sums(state,l.full_a[av as usize],l.full_s[sv as usize]);
    let la=av.wrapping_add(l.last_a);
    let ls=sv.wrapping_add(l.last_s);
    let(mut support,mut mask,mut raw)=(0u8,0u8,0u16);
    if l.route==3{
        for i in 0..5usize{
            let mut st=pre;
            let mut q=[0u8;3];
            for j in 0..3{
                st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));
                q[j]=st as u8;
            }
            if q[0]>=0xc0{continue}
            let v=((q[1]as u16)<<8)|q[2]as u16;
            if shiny(v){
                support=support.saturating_add(DEEP_WEIGHT[i]);
                mask|=1<<i;
                if raw==0{raw=v}
            }
        }
        if support<MIN_SUPPORT_WEIGHT{return None}
    }else{
        let mut st=pre;
        let mut q=[0u8;4];
        for j in 0..4{
            st=upd(st,la.wrapping_add(EMP_R4_A[j]),ls.wrapping_add(EMP_R4_S[j]));
            q[j]=st as u8;
        }
        if q[0]<0xc0{return None}
        let v=((q[2]as u16)<<8)|q[3]as u16;
        if !shiny(v){return None}
        support=4;mask=1;raw=v
    }
    let s40=apply_sums(state,l.p40_a[av as usize],l.p40_s[sv as usize]);
    let d40=((av.wrapping_add(l.o40a)as u16)<<8)|sv.wrapping_add(l.o40s)as u16;
    let s716=apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]);
    let d716=((av.wrapping_add(l.o716a)as u16)<<8)|sv.wrapping_add(l.o716s)as u16;
    let d717=((av.wrapping_add(l.o717a)as u16)<<8)|sv.wrapping_add(l.o717s)as u16;
    let s717=upd(s716,(d717>>8)as u8,d717 as u8);
    Some(Prediction{
        lane_id:l.id,source:l.source,support_weight:support,shiny_mask:mask,raw,
        expected40_state:s40,expected40_div:d40,
        expected716_state:s716,expected716_div:d716,
        expected717_state:s717,expected717_div:d717
    })
}

'''
p = p.replace(anchor, helper + anchor, 1)

# -------------------------------------------------------------------------
# 2) Replace v7.3.x control scanner with a real shiny scanner.
#    Only exact current A/r10 + bucket76 is evaluated. The chosen C/r8 donor
#    itself performs the DV calculation and returns only shiny candidates.
# -------------------------------------------------------------------------
a, b = fspan(t, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)')
monitor = f'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {{
        if !self.practical_scan_enabled
            || !self.practical_live_scan
            || self.probe_session
            || self.practical_active
            || self.practical_candidate_valid
        {{ return; }}

        let cur = rng_advance();
        if cur == self.practical_live_last_advance {{ return; }}
        self.practical_live_last_advance = cur;
        self.practical_live_checked = self.practical_live_checked.saturating_add(1);

        let r = latest_pre_vblank_ring();
        let n = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n != PRE_VBLANK_RING_LEN {{
            self.phase_now_proto = b'?';
            self.phase_now_lag = 0xff;
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        }}
        let (last, _) = pre_ring_sample(&r, n - 1);
        let lag = cur.wrapping_sub(last);
        let (proto0, mut rot, best, second, ok) = classify_pre_ring(&r);
        self.phase_best_score = best;
        self.phase_second_score = second;
        self.phase_consecutive = ok;
        if lag > 1 || !ok {{
            self.phase_now_proto = proto0;
            self.phase_now_rot = rot;
            self.phase_now_lag = lag.min(255) as u8;
            return;
        }}
        if lag == 1 {{ rot = rot.wrapping_add(1) & 15; }}
        self.phase_now_proto = proto0;
        self.phase_now_rot = rot;
        self.phase_now_lag = lag as u8;
        if lag != 0 || best != 0 {{ return; }}
        self.phase_exact_count = self.phase_exact_count.saturating_add(1);

        // The prototype is stable for an epoch. This build only has a causal
        // bucket model for A/r10, so non-A epochs still request a VC reset.
        if proto0 != b'A' {{
            self.phase_target_proto = proto0;
            self.phase_target_rot = rot;
            self.practical_live_found_advance = cur;
            self.practical_live_found_state = reader.rng_state();
            self.practical_live_found_div = measured_div();
            self.practical_live_found_lane = 254;
            self.practical_live_found_tick = pnp::system_tick();
            self.practical_live_found_ai = 0;
            self.practical_live_found_si = 0;
            self.practical_live_scan = false;
            self.practical_scan_enabled = false;
            self.practical_candidate_valid = false;
            self.practical_active = false;
            pnp::request_pause();
            return;
        }}
        if rot != 10 {{ return; }}

        let (_, p0) = pre_ring_sample(&r, 0);
        let pd = p0.wrapping_sub(0x0035) & 0x3fff;
        if (pd & 0x003f) != 0 {{ return; }}
        let bucket = ((pd >> 6) & 0x00ff) as u8;
        if bucket != {TARGET_BUCKET} {{ return; }}
        self.phase_target_count = self.phase_target_count.saturating_add(1);

        let Some(ai0) = add_div_tracker().index() else {{
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        }};
        let Some(si0) = sub_div_tracker().index() else {{
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        }};
        let ai=(ai0 as u32)&0x3fff;
        let si=(si0 as u32)&0x3fff;
        let state=reader.rng_state();
        let div=measured_div();
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);
        let Some(prediction)=practical::evaluate_empirical_post(
            b'A',10,b'{TARGET_POST_PROTO}',{TARGET_POST_ROT},state,div,ai,si
        ) else {{ return; }};

        // Prediction is already shiny. Keep lane253 as the v7.3 PauseRootLock
        // transport sentinel; bind_practical_prediction retains the real donor
        // lane/source/raw DV for Stage3 validation and CSV telemetry.
        self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);
        self.phase_target_proto=b'A';
        self.phase_target_rot=10;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=state;
        self.practical_live_found_div=div;
        self.practical_live_found_lane=253;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai;
        self.practical_live_found_si=si;
        self.practical_live_scan=false;
        self.practical_scan_enabled=false;
        self.clear_transport_diag();
        self.bind_practical_prediction(prediction);
        self.practical_empirical=true;
        pnp::request_pause();
    }}
'''
t = t[:a] + monitor + t[b:]

# -------------------------------------------------------------------------
# 3) Pack authoritative phase bucket into control_pause_cell().
#    bit28 = bucket valid, bits12..19 = bucket. Existing proto/rot bits remain.
# -------------------------------------------------------------------------
a, b = fspan(t, '    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32')
control = '''    pub fn control_pause_cell(&mut self, reader: &Gen2Reader) -> u32 {
        let mut out = 0u32;
        if self.practical_live_found_lane == 253 && !self.probe_session { out |= 1u32 << 31; }
        if self.practical_live_found_lane == 254 && !self.probe_session { out |= 1u32 << 30; }

        let r = latest_pre_vblank_ring();
        let count = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        let (proto, rot, best, second, consecutive) = classify_pre_ring(&r);
        self.phase_now_proto = proto;
        self.phase_now_rot = rot;
        self.phase_best_score = best;
        self.phase_second_score = second;
        self.phase_consecutive = consecutive;

        if count == PRE_VBLANK_RING_LEN && consecutive && best == 0 {
            out |= 1u32 << 29;
            out |= proto as u32;
            out |= (rot as u32) << 8;
            let (_, p0) = pre_ring_sample(&r, 0);
            let pd = p0.wrapping_sub(0x0035) & 0x3fff;
            if (pd & 0x003f) == 0 {
                let bucket = ((pd >> 6) & 0x00ff) as u32;
                out |= 1u32 << 28;
                out |= bucket << 12;
            }

            if self.practical_live_found_lane == 253 && !self.probe_session {
                self.phase_target_proto = proto;
                self.phase_target_rot = rot;
                self.practical_live_found_advance = rng_advance();
                self.practical_live_found_state = reader.rng_state();
                self.practical_live_found_div = measured_div();
                self.practical_live_found_tick = pnp::system_tick();
            }
        }
        out
    }
'''
t = t[:a] + control + t[b:]

# -------------------------------------------------------------------------
# 4) C PauseRootLock now locks A/r10 AND bucket76. A full 256-bucket traversal
#    can require up to 4096 neutral frames if the observed +37/16F cadence is
#    correct, so allow 4608 frames as a bounded experimental ceiling.
# -------------------------------------------------------------------------
m = rep(m, '#define SUICUNE_ROOT_LOCK_MAX_STEPS 64U',
        '#define SUICUNE_ROOT_LOCK_MAX_STEPS 4608U', 'increase bucket lock horizon')

old = '''            u32 proto = cell & 0xffU;\n            u32 rot = (cell >> 8) & 0x0fU;\n            suicune_root_lock_last_cell = cell;'''
new = f'''            u32 proto = cell & 0xffU;\n            u32 rot = (cell >> 8) & 0x0fU;\n            bool bucket_valid = (cell & 0x10000000U) != 0;\n            u32 bucket = (cell >> 12) & 0xffU;\n            suicune_root_lock_last_cell = cell;'''
m = rep(m, old, new, 'parse packed bucket')

m = rep(m,
        "if (valid && proto == (u32)'A' && rot == 10U)",
        f"if (valid && bucket_valid && proto == (u32)'A' && rot == 10U && bucket == {TARGET_BUCKET}U)",
        'lock A/r10 plus bucket')

# SLOT1 is part of the model. X is consumed but cannot invalidate the forecast.
if '(suicune_phase_slot == 1) ? 6 : 1' in m:
    m = m.replace('suicune_phase_slot = (suicune_phase_slot == 1) ? 6 : 1;',
                  'suicune_phase_slot = 1;', 1)

scan_reset = '''                suicune_root_lock_last_cell = 0;\n                search_suicune_practical_targets();'''
if scan_reset in m:
    m = m.replace(scan_reset,
                  '''                suicune_root_lock_last_cell = 0;\n                suicune_phase_slot = 1;\n                search_suicune_practical_targets();''', 1)

# -------------------------------------------------------------------------
# 5) User-visible/CSV telemetry. The prediction remains a probe: actual POST
#    and raw DV are still captured so a miss directly falsifies one model stage.
# -------------------------------------------------------------------------
t = t.replace('S733 ROOTLOCK SCAN', 'S734 SHINY B76 SCAN')
t = t.replace('S733 A/r10 LOCKED', 'S734 B76 SHINY LOCK')
t = t.replace('ABS SLOT{} X=TOGGLE', 'ABS SLOT{} FIXED')

close = '        pnp::trace_file_close();'
if t.count(close) != 1:
    raise SystemExit(f'v734 CSV close anchor expected 1, got {t.count(close)}')
row = f'''        line.clear();\n        let _ = write!(line,\n            "\\nphasebucket_shiny,version,target_bucket,expected_post_proto,expected_post_rot,wanted_slot,pred_raw,pred_lane,pred_source\\nPHASEBUCKET,V734,{TARGET_BUCKET},{TARGET_POST_PROTO},{TARGET_POST_ROT},1,{{:04X}},{{}},{{}}\\n",\n            self.practical_raw, self.practical_lane, self.practical_source\n        );\n        pnp::trace_file_write(line.as_bytes());\n\n'''
t = t.replace(close, row + close, 1)

P.write_text(p)
T.write_text(t)
M.write_text(m)
print('Applied Suicune v7.3.4 PhaseBucket Shiny Probe: A/r10 bucket76 -> C/r8, SLOT1, predicted shiny only')
