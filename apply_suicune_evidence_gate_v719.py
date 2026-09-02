#!/usr/bin/env python3
from pathlib import Path

TRACE=Path('reader_core/src/crystal/trace.rs')
PRACTICAL=Path('reader_core/src/crystal/practical.rs')
FRAME=Path('reader_core/src/crystal/frame.rs')

def need(s,m,label):
    if m not in s:
        raise SystemExit(f'v719 missing {label}: {m}')

def rust_span(s, signature):
    start=s.find(signature)
    if start<0:
        raise SystemExit(f'v719 missing fn {signature}')
    b=s.find('{',start)
    if b<0:
        raise SystemExit(f'v719 missing body {signature}')
    depth=0
    for i in range(b,len(s)):
        if s[i]=='{': depth+=1
        elif s[i]=='}':
            depth-=1
            if depth==0:
                e=i+1
                while e<len(s) and s[e] in ' \t': e+=1
                if e<len(s) and s[e]=='\n': e+=1
                return start,e
    raise SystemExit(f'v719 unclosed fn {signature}')

p=PRACTICAL.read_text()
marker="pub fn empirical_has_pre(p:u8,r:u8)->bool"
need(p,marker,'empirical evidence anchor')
evidence="""/// Hardware-evidence gate for production READY.\n///\n/// `true` means this PRE has already produced an actual rel40 POST that\n/// disagrees with a registered runtime donor path. Such roots remain useful\n/// for diagnostics/LEARN, but a branch-specific shiny forecast is not strong\n/// enough to stop the user at production READY.\n///\n/// A/r3  : registered B/r8, observed A/r12 (trace 0122)\n/// A/r10 : registered B/r9 + C/r8; observed A/r2, B/r14, D/r2, D/r15\n/// B/r11 : registered D/r2 + C/r2; observed A/r2, C/r3, D/r13\n/// D/r12 : registered C/r2; observed A/r2 (trace 0120)\n/// B/r1  : registered A/r2; observed B/r9 (trace 0092)\npub fn pre_has_observed_branch_conflict(proto: u8, rot: u8) -> bool {\n    matches!(\n        (proto, rot),\n        (b'A', 3) | (b'A', 10) | (b'B', 11) | (b'D', 12) | (b'B', 1)\n    )\n}\n\n"""
p=p.replace(marker,evidence+marker,1)
PRACTICAL.write_text(p)

t=TRACE.read_text()
need(t,'practical_scan_enabled','v718 scan gate')
need(t,'fn practical_wait_monitor','old live monitor')
need(t,'self.practical_wait_monitor(reader);','monitor call')
field_anchor='    practical_empirical_candidates: u32,\n'
need(t,field_anchor,'evidence field anchor')
t=t.replace(field_anchor,field_anchor+'    practical_evidence_reject: u32,\n',1)
init_anchor='            practical_empirical_candidates: 0,\n'
need(t,init_anchor,'evidence init anchor')
t=t.replace(init_anchor,init_anchor+'            practical_evidence_reject: 0,\n',1)
reset_anchor='        self.practical_empirical_candidates = 0;\n'
need(t,reset_anchor,'evidence reset anchor')
t=t.replace(reset_anchor,reset_anchor+'        self.practical_evidence_reject = 0;\n')

t=t.replace(
    'pub fn search_practical_targets(&mut self, _reader: &Gen2Reader)',
    'pub fn start_practical_scan(&mut self, _reader: &Gen2Reader)',1)

new_monitor="""    fn live_root_monitor(&mut self, reader: &Gen2Reader) {\n        if !self.practical_scan_enabled\n            || !self.practical_live_scan\n            || self.probe_session\n            || self.practical_active\n            || self.practical_candidate_valid\n        {\n            return;\n        }\n\n        let cur = rng_advance();\n        if cur == self.practical_live_last_advance {\n            return;\n        }\n        self.practical_live_last_advance = cur;\n        self.practical_live_checked = self.practical_live_checked.saturating_add(1);\n\n        let Some((proto, rot)) = self.live_pre_cell() else {\n            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);\n            return;\n        };\n\n        let proven = practical::lane_for_pre(proto, rot);\n        let empirical = practical::empirical_has_pre(proto, rot);\n        if proven.is_some() {\n            self.practical_live_lane_frames = self.practical_live_lane_frames.saturating_add(1);\n        }\n        if empirical {\n            self.practical_empirical_cell_frames =\n                self.practical_empirical_cell_frames.saturating_add(1);\n        }\n        if proven.is_none() && !empirical {\n            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);\n            return;\n        }\n\n        let Some(ai0) = add_div_tracker().index() else {\n            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);\n            return;\n        };\n        let Some(si0) = sub_div_tracker().index() else {\n            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);\n            return;\n        };\n        let ai = (ai0 as u32) & 0x3fff;\n        let si = (si0 as u32) & 0x3fff;\n        let state = reader.rng_state();\n        let div = measured_div();\n\n        let mut proven_prediction = None;\n        if let Some(id) = proven {\n            self.practical_live_exact_eval = self.practical_live_exact_eval.saturating_add(1);\n            proven_prediction = practical::evaluate_exact(id, state, div, ai, si);\n        }\n\n        let mut empirical_prediction = None;\n        let mut empirical_evaluated = !empirical;\n        if empirical {\n            if !practical::empirical_window_safe(ai, si) {\n                self.practical_empirical_skip_exception =\n                    self.practical_empirical_skip_exception.saturating_add(1);\n            } else {\n                empirical_evaluated = true;\n                self.practical_empirical_eval = self.practical_empirical_eval.saturating_add(1);\n                empirical_prediction =\n                    practical::evaluate_empirical(proto, rot, state, div, ai, si);\n                if empirical_prediction.is_some() {\n                    self.practical_empirical_candidates =\n                        self.practical_empirical_candidates.saturating_add(1);\n                }\n            }\n        }\n\n        let known_models = (proven.is_some() as u8) + (empirical as u8);\n        let shiny_models =\n            (proven_prediction.is_some() as u8) + (empirical_prediction.is_some() as u8);\n\n        // A shiny forecast from an already-conflicted PRE is diagnostic only.\n        // This blocks every currently known false READY family in 0080,\n        // 0088-0095 and 0120-0122 without inventing a new branch predictor.\n        if practical::pre_has_observed_branch_conflict(proto, rot) {\n            if shiny_models != 0 {\n                self.practical_evidence_reject =\n                    self.practical_evidence_reject.saturating_add(1);\n            }\n            return;\n        }\n\n        // If a known model could not be evaluated safely, do not manufacture\n        // consensus from the remaining model.\n        if !empirical_evaluated {\n            if shiny_models != 0 {\n                self.practical_evidence_reject =\n                    self.practical_evidence_reject.saturating_add(1);\n            }\n            return;\n        }\n\n        // Future-proofing: once multiple donor models exist for a PRE, all\n        // known models must agree on shiny. "Any lane is shiny" is no longer\n        // a production READY criterion.\n        if shiny_models == 0 {\n            return;\n        }\n        if shiny_models != known_models {\n            self.practical_evidence_reject =\n                self.practical_evidence_reject.saturating_add(1);\n            return;\n        }\n\n        let prediction = proven_prediction.or(empirical_prediction).unwrap();\n        self.practical_live_found_advance = cur;\n        self.practical_live_found_state = state;\n        self.practical_live_found_div = div;\n        self.practical_live_found_lane = prediction.lane_id;\n        self.practical_live_found_tick = pnp::system_tick();\n        self.practical_live_found_ai = ai;\n        self.practical_live_found_si = si;\n        self.practical_live_scan = false;\n        self.practical_scan_enabled = false;\n        self.bind_practical_prediction(prediction);\n        self.practical_empirical = prediction.lane_id >= 101;\n        pnp::request_pause();\n    }\n"""
a,b=rust_span(t,'    fn practical_wait_monitor')
t=t[:a]+new_monitor+t[b:]
t=t.replace('self.practical_wait_monitor(reader);','self.live_root_monitor(reader);',1)

t=t.replace('"S718 ','"S719 ')
t=t.replace('PRACTICAL,V718','PRACTICAL,V719')
old_fmt='"EV{} SK{}"'
old_args='self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception));'
if old_fmt in t and old_args in t:
    t=t.replace(old_fmt,'"EV{} SK{} RJ{}"',1)
    t=t.replace(old_args,'self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception), self.practical_evidence_reject);',1)

old_learn='pnp::println!("S719 LEARN P{:02X} R{}",self.practical_post_proto,self.practical_post_rot);'
if old_learn in t:
    t=t.replace(old_learn,'pnp::println!("S719 LEARN ONLY"); pnp::println!("P{:02X} R{}",self.practical_post_proto,self.practical_post_rot);',1)

stage='            let _=write!(line,"STAGE3,V710,'
need(t,stage,'STAGE3 telemetry anchor')
ins='            let _=write!(line,"EVIDENCE,V719,{}\\n",self.practical_evidence_reject);pnp::trace_file_write(line.as_bytes());line.clear();\n'
t=t.replace(stage,ins+stage,1)
TRACE.write_text(t)

f=FRAME.read_text()
need(f,'state.trace.search_practical_targets(&reader);','frame scan call')
f=f.replace('state.trace.search_practical_targets(&reader);','state.trace.start_practical_scan(&reader);',1)
FRAME.write_text(f)

print('Applied Suicune v7.1.9 EvidenceGate: branch-conflicted PREs are diagnostic-only; multi-model READY requires consensus')
