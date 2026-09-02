#!/usr/bin/env python3
from pathlib import Path

P = Path('reader_core/src/crystal/practical.rs')
T = Path('reader_core/src/crystal/trace.rs')


def need(text, marker, label):
    if marker not in text:
        raise SystemExit(f'v713 missing {label}: {marker}')


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'v713 {label}: expected 1 match, found {n}')
    return text.replace(old, new, 1)


p = P.read_text()
t = T.read_text()

# v7.1.3 deliberately keeps the v6.8 actual-root scanner.  The change is only
# at rel40: if Exact2F lands in a different *known* POST branch, allow a
# cross-family rebind between the proven v7.0 lanes and the empirical v7.1
# lanes instead of declaring MISS1 immediately.
for marker, label in [
    ('pub fn evaluate_exact', 'v7.0 exact evaluator'),
    ('pub fn evaluate_post_exact', 'v7.0 post exact evaluator'),
    ('const EMP_LANES', 'v7.1 empirical lanes'),
    ('pub fn evaluate_empirical', 'v7.1 empirical evaluator'),
    ('S712 SCAN', 'v7.1.2 UI'),
    ('fn practical_wait_monitor', 'actual-root monitor'),
    ('STAGE3,V710', 'stage3 telemetry'),
]:
    need(p if 'evaluate' in marker or 'EMP_' in marker else t, marker, label)

# Helpers exposed inside practical.rs.  prediction_pre() gives the PRE cell of
# whichever lane caused READY.  empirical_lane_for_pre_post() is intentionally
# unique-only: ambiguous empirical suffixes are not guessed.
anchor = "pub fn empirical_post(id:u8)->Option<(u8,u8,u16,u8)>{emp_lane(id).map(|x|(x.post_proto,x.post_rot,x.source,x.route))}\n"
insert = anchor + r'''pub fn prediction_pre(id:u8)->Option<(u8,u8)>{
 if let Some(l)=emp_lane(id){return Some((l.pre_proto,l.pre_rot))}
 if id>=1&&id<=LANE_COUNT{let l=lane(id);return Some((l.pre_proto,l.pre_rot))}
 None
}
pub fn empirical_lane_for_pre_post(pp:u8,pr:u8,op:u8,orot:u8)->Option<u8>{
 let mut found=0u8;let mut count=0u8;
 for l in EMP_LANES.iter(){if l.pre_proto==pp&&l.pre_rot==pr&&l.post_proto==op&&l.post_rot==orot{found=l.id;count=count.saturating_add(1)}}
 if count==1{Some(found)}else{None}
}
'''
p = replace_once(p, anchor, insert, 'practical helper insertion')

# Re-evaluate an empirical suffix from the *actual* rel40 state.  The empirical
# tables are cumulative from Target; subtracting p40 from p716/full gives the
# exact measured suffix for that donor.  We reconstruct the Target DivTracker
# index only to preserve the existing no-cadence-exception safety rule.
post_eval = r'''
pub fn evaluate_empirical_post(id:u8,state40:u16,div40:u16,ai40:u32,si40:u32)->Option<Prediction>{
 let l=emp_lane(id)?;
 let tai=ai40.wrapping_sub(41)&0x3fff;let tsi=si40.wrapping_sub(41)&0x3fff;
 if !empirical_window_safe(tai,tsi){return None}
 let a40=(div40>>8)as u8;let s40=div40 as u8;
 let av0=a40.wrapping_sub(l.o40a);let sv0=s40.wrapping_sub(l.o40s);
 let sa716=l.p716_a[av0 as usize].wrapping_sub(l.p40_a[av0 as usize]);
 let ss716=l.p716_s[sv0 as usize].wrapping_sub(l.p40_s[sv0 as usize]);
 let s716=apply_sums(state40,sa716,ss716);
 let a716=av0.wrapping_add(l.o716a);let d716s=sv0.wrapping_add(l.o716s);
 let d716=((a716 as u16)<<8)|d716s as u16;
 let a717=av0.wrapping_add(l.o717a);let d717s=sv0.wrapping_add(l.o717s);
 let d717=((a717 as u16)<<8)|d717s as u16;let s717=upd(s716,a717,d717s);
 let safull=l.full_a[av0 as usize].wrapping_sub(l.p40_a[av0 as usize]);
 let ssfull=l.full_s[sv0 as usize].wrapping_sub(l.p40_s[sv0 as usize]);
 let pre=apply_sums(state40,safull,ssfull);
 let la=av0.wrapping_add(l.last_a);let ls=sv0.wrapping_add(l.last_s);
 let(mut support,mut mask,mut raw)=(0u8,0u8,0u16);
 if l.route==3{
  for i in 0..5usize{let mut st=pre;let mut q=[0u8;3];for j in 0..3{st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));q[j]=st as u8}if q[0]>=0xc0{continue}let v=((q[1]as u16)<<8)|q[2]as u16;if shiny(v){support=support.saturating_add(DEEP_WEIGHT[i]);mask|=1<<i;if raw==0{raw=v}}}
  if support<MIN_SUPPORT_WEIGHT{return None}
 }else{
  let mut st=pre;let mut q=[0u8;4];for j in 0..4{st=upd(st,la.wrapping_add(EMP_R4_A[j]),ls.wrapping_add(EMP_R4_S[j]));q[j]=st as u8}if q[0]<0xc0{return None}let v=((q[2]as u16)<<8)|q[3]as u16;if !shiny(v){return None}support=4;mask=1;raw=v
 }
 Some(Prediction{lane_id:l.id,source:l.source,support_weight:support,shiny_mask:mask,raw,expected40_state:state40,expected40_div:div40,expected716_state:s716,expected716_div:d716,expected717_state:s717,expected717_div:d717})
}
'''
needle = "\nfn edist(a:u32,b:u32)->u32{b.wrapping_sub(a)&0x3fff}\n"
p = replace_once(p, needle, post_eval + needle, 'empirical post evaluator')
P.write_text(p)

# Shared cross-branch resolver inserted into Trace.  Proven POST lanes use the
# exact-index suffix evaluator.  Empirical POST lanes are only considered when
# they share the READY lane's PRE cell, so C/r2 donors from unrelated PRE cells
# cannot be accidentally substituted.
method_anchor = "    fn enter_stage3_learn(&mut self,p:u8,r:u8){"
need(t, method_anchor, 'stage3 learn method')
resolver = r'''    fn rebind_known_post_v713(&mut self,post_proto:u8,post_rot:u8,state40:u16,div40:u16)->bool{
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
t = replace_once(t, method_anchor, resolver + method_anchor, 'trace cross resolver')

# Empirical path: direct branch/state match keeps the existing path.  Any
# mismatch first asks the cross resolver; only then fall back to D/r15 LEARN or
# MISS1.  This also repairs a same-POST state drift from the actual rel40 state.
old_emp = "let ok=if let Some((p,r,_,_))=practical::empirical_post(self.practical_lane){post.valid&&post.best_score==0&&post.proto==p&&post.rot40==r}else{false};if !ok||e.state!=self.practical_expected40_state||e.div!=self.practical_expected40_div{if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}"
new_emp = "let ok=if let Some((p,r,_,_))=practical::empirical_post(self.practical_lane){post.valid&&post.best_score==0&&post.proto==p&&post.rot40==r}else{false};if !ok||e.state!=self.practical_expected40_state||e.div!=self.practical_expected40_div{if post.valid&&post.best_score==0&&self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40)}else{self.practical_fail(1)}return}"
t = replace_once(t, old_emp, new_emp, 'empirical rel40 cross rebind')

# Proven path: replace the old proven-only rebind block with the same shared
# resolver.  This is the key A/r10 rescue: a READY from proven 0095 can now
# rebind at rel40 to empirical 0098/C-r8 when that is the branch actually seen.
old_proven = "if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40);return}if post.valid&&post.best_score==0{if let Some(id)=practical::lane_for_post_unique(post.proto,post.rot40){let Some(ai)=add_div_tracker().index()else{self.practical_fail(1);return};let Some(si)=sub_div_tracker().index()else{self.practical_fail(1);return};if let Some(x)=practical::evaluate_post_exact(id,e.state,e.div,(ai as u32)&0x3fff,(si as u32)&0x3fff){self.rebind_practical_post_v690(x,post.proto,post.rot40)}else{self.practical_fail(1);return}}else{self.practical_fail(1);return}}else{self.practical_fail(1);return}"
new_proven = "if post.valid&&post.best_score==0&&self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div){return}if post.valid&&post.best_score==0&&post.proto==b'D'&&post.rot40==15{self.enter_stage3_learn(post.proto,post.rot40);return}self.practical_fail(1);return"
t = replace_once(t, old_proven, new_proven, 'proven rel40 cross rebind')

# UI epoch only.  CSV keeps V710 for parser compatibility, as v7.1.2 did.
t = t.replace('"S712 ', '"S713 ')
T.write_text(t)
print('Applied Suicune v7.1.3 CrossBranch: actual-root scan retained; proven/empirical rel40 rebind unified')
