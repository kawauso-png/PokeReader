#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/practical.rs')
T = Path('reader_core/src/crystal/trace.rs')


def need(text, marker, label):
    if marker not in text:
        raise SystemExit(f'v720 missing {label}: {marker}')


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'v720 {label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)


p = P.read_text()
t = T.read_text()

for marker, label in [
    ('pub fn empirical_lane_for_pre_post', 'v713 empirical pre/post helper'),
    ('pub fn evaluate_empirical_post', 'v713 empirical suffix evaluator'),
    ('pub fn lane_for_post_unique', 'proven POST helper'),
    ('fn rebind_known_post_v713', 'v713 cross-branch resolver'),
    ('S713 SCAN', 'v713 UI epoch'),
    ('STAGE3,V710', 'stage3 telemetry'),
]:
    need(p if 'pub fn' in marker else t, marker, label)

# ---------------------------------------------------------------------------
# v7.2 validation premise:
# POST is treated as a global downstream class.  PRE is retained as telemetry
# only; it is NOT required for selecting a unique empirical POST donor.
# This does not turn ambiguous POST classes into predictions.  Ambiguous or
# unseen classes are sent to LEARN so a complete trace can be collected.
# ---------------------------------------------------------------------------
helper_anchor = r'''pub fn empirical_lane_for_pre_post(pp:u8,pr:u8,op:u8,orot:u8)->Option<u8>{
 let mut found=0u8;let mut count=0u8;
 for l in EMP_LANES.iter(){if l.pre_proto==pp&&l.pre_rot==pr&&l.post_proto==op&&l.post_rot==orot{found=l.id;count=count.saturating_add(1)}}
 if count==1{Some(found)}else{None}
}
'''
helper_insert = helper_anchor + r'''pub fn empirical_post_count_global(op:u8,orot:u8)->u8{
 let mut count=0u8;
 for l in EMP_LANES.iter(){if l.post_proto==op&&l.post_rot==orot{count=count.saturating_add(1)}}
 count
}
pub fn empirical_lane_for_post_unique_global(op:u8,orot:u8)->Option<u8>{
 let mut found=0u8;let mut count=0u8;
 for l in EMP_LANES.iter(){if l.post_proto==op&&l.post_rot==orot{found=l.id;count=count.saturating_add(1)}}
 if count==1{Some(found)}else{None}
}
pub fn proven_post_count(proto:u8,rot:u8)->u8{
 let mut count=0u8;
 for id in 1..=LANE_COUNT{let l=lane(id);if l.post_proto==proto&&l.post_rot==rot{count=count.saturating_add(1)}}
 count
}
pub fn post_evidence_counts(proto:u8,rot:u8)->(u8,u8){
 (proven_post_count(proto,rot),empirical_post_count_global(proto,rot))
}
'''
p = replace_once(p, helper_anchor, helper_insert, 'global POST helper insertion')
P.write_text(p)

old_resolver = r'''    fn rebind_known_post_v713(&mut self,post_proto:u8,post_rot:u8,state40:u16,div40:u16)->bool{
        let origin_pre=practical::prediction_pre(self.practical_lane);
        if let Some(id)=practical::lane_for_post_unique(post_proto,post_rot){
            if let (Some(ai),Some(si))=(add_div_tracker().index(),sub_div_tracker().index()){
                if let Some(x)=practical::evaluate_post_exact(id,state40,div40,(ai as u32)&0x3fff,(si as u32)&0x3fff){
                    self.practical_empirical=false;
                    self.rebind_practical_post_v690(x,post_proto,post_rot);
                    return true;
                }
            }
        }
        if let Some((pp,pr))=origin_pre{
            if let Some(id)=practical::empirical_lane_for_pre_post(pp,pr,post_proto,post_rot){
                if let (Some(ai),Some(si))=(add_div_tracker().index(),sub_div_tracker().index()){
                    if let Some(x)=practical::evaluate_empirical_post(id,state40,div40,(ai as u32)&0x3fff,(si as u32)&0x3fff){
                        self.practical_empirical=true;
                        self.rebind_practical_post_v690(x,post_proto,post_rot);
                        return true;
                    }
                }
            }
        }
        false
    }
'''
new_resolver = r'''    fn rebind_known_post_v720(&mut self,post_proto:u8,post_rot:u8,state40:u16,div40:u16)->bool{
        // Proven exact POST classes remain first choice.
        if let Some(id)=practical::lane_for_post_unique(post_proto,post_rot){
            if let (Some(ai),Some(si))=(add_div_tracker().index(),sub_div_tracker().index()){
                if let Some(x)=practical::evaluate_post_exact(id,state40,div40,(ai as u32)&0x3fff,(si as u32)&0x3fff){
                    self.practical_empirical=false;
                    self.rebind_practical_post_v690(x,post_proto,post_rot);
                    return true;
                }
            }
        }
        // v7.2 VALIDATION ONLY: empirical POST identity is global, not PRE-bound.
        // We still require uniqueness.  Multiple empirical suffixes are never
        // guessed; they fall through to LEARN below.
        if let Some(id)=practical::empirical_lane_for_post_unique_global(post_proto,post_rot){
            if let (Some(ai),Some(si))=(add_div_tracker().index(),sub_div_tracker().index()){
                if let Some(x)=practical::evaluate_empirical_post(id,state40,div40,(ai as u32)&0x3fff,(si as u32)&0x3fff){
                    self.practical_empirical=true;
                    self.rebind_practical_post_v690(x,post_proto,post_rot);
                    return true;
                }
            }
        }
        false
    }
'''
t = replace_once(t, old_resolver, new_resolver, 'POST-centric resolver')

old_emp = "let ok=if let Some((p,r,_,_))=practical::empirical_post(self.practical_lane){post.valid&&post.best_score==0&&post.proto==p&&post.rot40==r}else{false};if !ok||e.state!=self.practical_expected40_state||e.div!=self.practical_expected40_div{if post.valid&&post.best_score==0&&self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}"
new_emp = "let ok=if let Some((p,r,_,_))=practical::empirical_post(self.practical_lane){post.valid&&post.best_score==0&&post.proto==p&&post.rot40==r}else{false};if !ok||e.state!=self.practical_expected40_state||e.div!=self.practical_expected40_div{if post.valid&&post.best_score==0&&self.rebind_known_post_v720(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}"
t = replace_once(t, old_emp, new_emp, 'empirical validation fallback')

old_proven = "if post.valid&&post.best_score==0&&self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40);return}self.practical_fail(1);return"
new_proven = "if post.valid&&post.best_score==0&&self.rebind_known_post_v720(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40);return}self.practical_fail(1);return"
t = replace_once(t, old_proven, new_proven, 'proven validation fallback')

# Add a compact POST evidence record.  PRE is logged only to measure whether it
# carries predictive information; it is not used by the v7.2 global resolver.
telemetry_marker = '            let _=write!(line,"STAGE3,V710,'
need(t, telemetry_marker, 'stage3 telemetry write')
telemetry = r'''            let (v720_pc,v720_ec)=if self.practical_post_proto!=0{practical::post_evidence_counts(self.practical_post_proto,self.practical_post_rot)}else{(0,0)};
            let (v720_pp,v720_pr)=practical::prediction_pre(self.practical_lane).unwrap_or((0,0));
            let _=write!(line,"POSTBEAM,V720,{:02X},{},{},{},{:02X},{},{}\n",self.practical_post_proto,self.practical_post_rot,v720_pc,v720_ec,v720_pp,v720_pr,self.practical_learn);pnp::trace_file_write(line.as_bytes());line.clear();
'''
t = t.replace(telemetry_marker, telemetry + telemetry_marker, 1)

# UI epoch: this branch is explicitly a validation build.  READY becomes TEST
# so it cannot be mistaken for a production-confidence shiny promise.
t = t.replace('"S713 ', '"S720 ')
t = t.replace('S720 READY UP+B', 'S720 TEST UP+B')
t = t.replace('S720 LEARN D15', 'S720 LEARN POST')
T.write_text(t)

print('Applied Suicune v7.2 POSTBEAM validation: global unique POST rebind; ambiguous/unseen POST -> LEARN; no probabilities')
