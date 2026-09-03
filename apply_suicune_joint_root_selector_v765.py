from pathlib import Path
P=Path('reader_core/src/crystal/practical.rs')
T=Path('reader_core/src/crystal/trace.rs')
p=P.read_text(); t=T.read_text()

# v7.6.5 Joint Root Selector
# PRE/root -> rel26 is projected directly. From rel26, enumerate observed
# (POST,J) centres, project each to rel40, then reuse the authoritative v7.6.3
# rel40 inverse-tail evaluator. A root locks only when two distinct joint
# hypotheses vote for the same shiny raw DV.

anchor='pub fn evaluate_multi_pre_inverse(proto:u8,rot:u8,bucket:Option<u8>,state:u16,div:u16,ai:u32,si:u32)->Option<MultiPrePrediction>{'
if anchor not in p: raise SystemExit('v765 practical insertion anchor missing')
insert=r'''
#[derive(Clone,Copy)]
pub struct JointRootPrediction{
    pub prediction:Prediction,
    pub score:u8,
    pub tested:u8,
    pub shiny_hypotheses:u8,
    pub raw_votes:u8,
    pub post_proto:u8,
    pub post_rot:u8,
    pub j_a:i16,
    pub j_s:i16,
    pub state40:u16,
    pub div40:u16,
}

#[derive(Clone,Copy)]
struct V765Joint{post_proto:u8,post_rot:u8,j_a:i16,j_s:i16}

const V765_JOINTS:[V765Joint;20]=[
    V765Joint{post_proto:b'D',post_rot:1,j_a:-581,j_s:-581},
    V765Joint{post_proto:b'D',post_rot:2,j_a:551,j_s:551},
    V765Joint{post_proto:b'C',post_rot:2,j_a:-555,j_s:-559},
    V765Joint{post_proto:b'A',post_rot:5,j_a:-152,j_s:-152},
    V765Joint{post_proto:b'C',post_rot:8,j_a:-150,j_s:-150},
    V765Joint{post_proto:b'D',post_rot:15,j_a:242,j_s:242},
    V765Joint{post_proto:b'D',post_rot:2,j_a:-145,j_s:-145},
    V765Joint{post_proto:b'A',post_rot:2,j_a:-148,j_s:-148},
    V765Joint{post_proto:b'C',post_rot:2,j_a:1457,j_s:1457},
    V765Joint{post_proto:b'B',post_rot:9,j_a:-145,j_s:-145},
    V765Joint{post_proto:b'C',post_rot:2,j_a:-17,j_s:-17},
    V765Joint{post_proto:b'D',post_rot:6,j_a:191,j_s:191},
    V765Joint{post_proto:b'D',post_rot:2,j_a:1513,j_s:1513},
    V765Joint{post_proto:b'B',post_rot:14,j_a:-501,j_s:-493},
    V765Joint{post_proto:b'B',post_rot:9,j_a:175,j_s:175},
    V765Joint{post_proto:b'C',post_rot:2,j_a:692,j_s:692},
    V765Joint{post_proto:b'B',post_rot:9,j_a:559,j_s:559},
    V765Joint{post_proto:b'C',post_rot:2,j_a:-350,j_s:-350},
    V765Joint{post_proto:b'B',post_rot:9,j_a:1713,j_s:1713},
    V765Joint{post_proto:b'B',post_rot:14,j_a:-4,j_s:3},
];

const V765_PHASE:[[i16;16];4]=[
    [1,-1,0,-1,2,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
    [-4,7,-3,0,-2,3,-1,2,1,-3,2,-1,-1,3,0,-3],
    [-2,1,1,-2,2,0,-1,0,1,-8,7,1,-4,4,0,0],
    [2,0,-2,2,-1,-1,-8,9,-1,-4,5,-1,0,-2,3,-1],
];

fn v765_phase(proto:u8,idx:usize)->i16{
    if !(b'A'..=b'D').contains(&proto){return 0}
    V765_PHASE[(proto-b'A')as usize][idx&15]
}

fn v765_allowed_rot(pp:u8,pr:u8,post_rot:u8)->bool{
    match (pp,pr){
        (b'A',14)=>(post_rot==2),
        (b'A',3)=>(post_rot==8),
        (b'A',10)=>matches!(post_rot,2|5|8|9|15),
        (b'A',6)=>(post_rot==2),
        (b'B',10)=>(post_rot==2),
        (b'B',11)=>(post_rot==2),
        (b'B',5)=>(post_rot==14),
        (b'B',1)=>(post_rot==2),
        (b'D',12)=>(post_rot==2),
        _=>false,
    }
}

fn v765_add_phase(x:u16,j:i16)->u16{((x as i32+1172+j as i32)&0x3fff)as u16}
fn v765_step(st:u16,ap:u16,sp:u16,ja:i16,js:i16)->(u16,u16,u16,u16){
    let na=v765_add_phase(ap,ja);let ns=v765_add_phase(sp,js);
    let d=(((na>>6)as u16)<<8)|((ns>>6)as u16);
    (upd(st,(d>>8)as u8,d as u8),na,ns,d)
}

fn v765_to_rel26(pp:u8,pr:u8,state:u16,ap4:u16,sp4:u16)->(u16,u16,u16,u16){
    let mut st=state;let mut ap=ap4&0x3fff;let mut sp=sp4&0x3fff;let mut d=0u16;
    for k in 0..27usize{
        let e=v765_phase(pp,(pr as usize+k)&15);
        let z=v765_step(st,ap,sp,e,e);st=z.0;ap=z.1;sp=z.2;d=z.3;
    }
    (st,ap,sp,d)
}

fn v765_project_rel40(rel26:(u16,u16,u16,u16),j:V765Joint)->(u16,u16){
    let(mut st,mut ap,mut sp,_)=rel26;
    let z=v765_step(st,ap,sp,j.j_a,j.j_s);st=z.0;ap=z.1;sp=z.2;
    let e=v765_phase(j.post_proto,(j.post_rot as usize+3)&15);
    let z=v765_step(st,ap,sp,e,e);st=z.0;ap=z.1;sp=z.2;
    for rel in 28usize..40usize{
        let e=v765_phase(j.post_proto,(j.post_rot as usize+4+(rel-28))&15);
        let z=v765_step(st,ap,sp,e,e);st=z.0;ap=z.1;sp=z.2;
    }
    let d=(((ap>>6)as u16)<<8)|((sp>>6)as u16);
    (st,d)
}

fn v765_raw_index(raw:u16)->Option<usize>{V762_SHINY_RAW.iter().position(|x|*x==raw)}

pub fn evaluate_joint_root_v765(
    pp:u8,pr:u8,state:u16,_div:u16,ap4:u16,sp4:u16,ai:u32,si:u32
)->Option<JointRootPrediction>{
    if !multipre_supported(pp,pr){return None}
    let rel26=v765_to_rel26(pp,pr,state,ap4,sp4);
    let ai40=ai.wrapping_add(41)&0x3fff;let si40=si.wrapping_add(41)&0x3fff;
    let mut tested=0u8;let mut hits=0u8;
    let mut votes=[0u8;8];let mut support=[0u16;8];
    let mut best_pred:[Option<Prediction>;8]=[None;8];
    let mut best_joint:[Option<V765Joint>;8]=[None;8];
    let mut best_state40=[0u16;8];let mut best_div40=[0u16;8];

    for j in V765_JOINTS.iter().copied(){
        if !v765_allowed_rot(pp,pr,j.post_rot){continue}
        let(base40,d40)=v765_project_rel40(rel26,j);
        let mut hyp_best:Option<(usize,Prediction,u16)>=None;
        let mut hyp_tested=false;
        for corr in 0u16..=3u16{
            let s40=(base40&0xff00)|(((base40 as u8).wrapping_add(corr as u8))as u16);
            let g=evaluate_actual_post_inverse_v763(j.post_proto,j.post_rot,s40,d40,ai40,si40);
            if g.evaluated!=0{hyp_tested=true}
            if let Some(x)=g.prediction{
                if let Some(ri)=v765_raw_index(x.raw){
                    match hyp_best{
                        None=>hyp_best=Some((ri,x,s40)),
                        Some((_,old,_))=>if x.support_weight>old.support_weight{hyp_best=Some((ri,x,s40))},
                    }
                }
            }
        }
        if hyp_tested{tested=tested.saturating_add(1)}
        if let Some((ri,x,s40))=hyp_best{
            hits=hits.saturating_add(1);votes[ri]=votes[ri].saturating_add(1);
            support[ri]=support[ri].saturating_add(x.support_weight as u16);
            let replace=best_pred[ri].map(|b|x.support_weight>b.support_weight).unwrap_or(true);
            if replace{best_pred[ri]=Some(x);best_joint[ri]=Some(j);best_state40[ri]=s40;best_div40[ri]=d40}
        }
    }

    let mut bi=None;let mut bv=0u8;let mut bs=0u16;
    for i in 0..8usize{
        if votes[i]>bv||(votes[i]==bv&&votes[i]!=0&&support[i]>bs){bi=Some(i);bv=votes[i];bs=support[i]}
    }
    let i=bi?;
    if bv<2{return None}
    let pred=best_pred[i]?;let j=best_joint[i]?;
    let score=((bv as u16)*32+(hits.saturating_sub(bv)as u16)*4+(bs/16)).min(100)as u8;
    Some(JointRootPrediction{prediction:pred,score,tested,shiny_hypotheses:hits,raw_votes:bv,
        post_proto:j.post_proto,post_rot:j.post_rot,j_a:j.j_a,j_s:j.j_s,
        state40:best_state40[i],div40:best_div40[i]})
}

'''
p=p.replace(anchor,insert+anchor,1)

old='''    multipre_score: u8,\n    multipre_branches: u8,\n    v763_rel40_state: u16,'''
new='''    multipre_score: u8,\n    multipre_branches: u8,\n    v765_joint_tested: u8,\n    v765_joint_hits: u8,\n    v765_joint_votes: u8,\n    v765_joint_j_a: i16,\n    v765_joint_j_s: i16,\n    v765_pred_state40: u16,\n    v765_pred_div40: u16,\n    v763_rel40_state: u16,'''
if old not in t: raise SystemExit('v765 trace fields anchor missing')
t=t.replace(old,new,1)
old='''            multipre_score: 0,\n            multipre_branches: 0,\n            v763_rel40_state: 0,'''
new='''            multipre_score: 0,\n            multipre_branches: 0,\n            v765_joint_tested: 0,\n            v765_joint_hits: 0,\n            v765_joint_votes: 0,\n            v765_joint_j_a: 0,\n            v765_joint_j_s: 0,\n            v765_pred_state40: 0,\n            v765_pred_div40: 0,\n            v763_rel40_state: 0,'''
if old not in t: raise SystemExit('v765 trace default anchor missing')
t=t.replace(old,new,1)
old='''        self.multipre_score = 0;\n        self.multipre_branches = 0;\n        self.v763_rel40_state = 0;'''
new='''        self.multipre_score = 0;\n        self.multipre_branches = 0;\n        self.v765_joint_tested = 0;\n        self.v765_joint_hits = 0;\n        self.v765_joint_votes = 0;\n        self.v765_joint_j_a = 0;\n        self.v765_joint_j_s = 0;\n        self.v765_pred_state40 = 0;\n        self.v765_pred_div40 = 0;\n        self.v763_rel40_state = 0;'''
if old not in t: raise SystemExit('v765 trace reset anchor missing')
t=t.replace(old,new,1)

a=t.index('    fn live_root_monitor(&mut self, reader: &Gen2Reader) {')
b=t.index('\n    fn practical_fail',a)
new_monitor=r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled||!self.practical_live_scan||self.probe_session||self.practical_active||self.practical_candidate_valid{return}
        let cur=rng_advance();let da=cur.wrapping_sub(self.practical_live_last_advance);if da==0{return}
        self.practical_live_last_advance=cur;self.practical_live_checked=self.practical_live_checked.saturating_add(1);
        let r=latest_pre_vblank_ring();let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);if n!=PRE_VBLANK_RING_LEN{return}
        let(last,_)=pre_ring_sample(&r,n-1);let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best;self.phase_second_score=second;self.phase_consecutive=ok;self.phase_now_proto=proto0;self.phase_now_rot=rot;self.phase_now_lag=lag.min(255)as u8;
        if lag==1{rot=rot.wrapping_add(1)&15}if lag!=0||!ok||best!=0{return}
        self.phase_exact_count=self.phase_exact_count.saturating_add(1);self.phase_now_rot=rot;
        if !practical::multipre_supported(proto0,rot){return}
        let Some(ai0)=add_div_tracker().index()else{self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);return};
        let Some(si0)=sub_div_tracker().index()else{self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);return};
        let ai=(ai0 as u32)&0x3fff;let si=(si0 as u32)&0x3fff;let state=reader.rng_state();let div=measured_div();
        let ap4=direct_phase_m((div>>8)as u8,adiv_subtick());let sp4=direct_phase_m(div as u8,sdiv_subtick());
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);
        if let Some(jp)=practical::evaluate_joint_root_v765(proto0,rot,state,div,ap4,sp4,ai,si){
            let x=jp.prediction;self.multipre_score=jp.score;self.multipre_branches=jp.shiny_hypotheses;
            self.v765_joint_tested=jp.tested;self.v765_joint_hits=jp.shiny_hypotheses;self.v765_joint_votes=jp.raw_votes;
            self.v765_joint_j_a=jp.j_a;self.v765_joint_j_s=jp.j_s;self.v765_pred_state40=jp.state40;self.v765_pred_div40=jp.div40;
            self.bucket_model_active=false;self.bucket_expected_post_proto=jp.post_proto;self.bucket_expected_post_rot=jp.post_rot;
            self.phase_target_proto=proto0;self.phase_target_rot=rot;self.practical_live_found_advance=cur;self.practical_live_found_state=state;self.practical_live_found_div=div;
            self.practical_live_found_tick=pnp::system_tick();self.practical_live_found_ai=ai;self.practical_live_found_si=si;
            self.bind_practical_prediction(x);self.practical_support=jp.score;self.practical_live_found_lane=253;self.practical_empirical=x.lane_id>=101&&x.lane_id<200;
            self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);self.practical_live_scan=false;pre_vblank_timing_capture_stop();pnp::request_pause();
        }
    }
'''
t=t[:a]+new_monitor+t[b:]

needle='''        line.clear();\n        let _=write!(line,"\\nrel40_gate,version,state40,div40,post_proto,post_rot,post_score,models,evaluated,shiny_models,gate_raw,gate_lane,gate_source,miss\\nREL40GATE,V763,{:04X},{:04X},{},{},{},{},{},{},{:04X},{},{},{}\\n",'''
if needle not in t: raise SystemExit('v765 CSV anchor missing')
row='''        line.clear();\n        let _=write!(line,"\\njoint_root,version,pre_proto,pre_rot,tested,shiny_hypotheses,raw_votes,score,pred_post_proto,pred_post_rot,j_a,j_s,pred_state40,pred_div40,pred_raw,target,miss\\nJOINTROOT,V765,{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{},{}\\n",\n            self.phase_target_proto as char,self.phase_target_rot,self.v765_joint_tested,self.v765_joint_hits,self.v765_joint_votes,self.multipre_score,\n            if self.bucket_expected_post_proto==0{'?'}else{self.bucket_expected_post_proto as char},self.bucket_expected_post_rot,self.v765_joint_j_a,self.v765_joint_j_s,\n            self.v765_pred_state40,self.v765_pred_div40,self.practical_raw,self.practical_target,self.practical_miss);\n        pnp::trace_file_write(line.as_bytes());\n\n'''
t=t.replace(needle,row+needle,1)

t=t.replace('pnp::println!("S763 PRE-HINT SCAN");','pnp::println!("S765 JOINT SCAN");',1)
t=t.replace('pnp::println!("Y+DOWN START 9 CELLS");','pnp::println!("Y+DOWN START JOINT");',1)
old='''                pnp::println!("S763 PRE HINT LOCK");\n                pnp::println!("PRE {}/r{} BR{}",self.phase_target_proto as char,self.phase_target_rot,self.multipre_branches);\n                pnp::println!("RANK {} T{}",self.multipre_score,self.practical_target);\n                pnp::println!("H{}/r{} DV{:04X}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.practical_raw);\n                pnp::println!("B -> RELEASE -> UP");'''
new='''                pnp::println!("S765 JOINT LOCK");\n                pnp::println!("PRE {}/r{} T{}",self.phase_target_proto as char,self.phase_target_rot,self.practical_target);\n                pnp::println!("TEST{} HIT{} V{}",self.v765_joint_tested,self.v765_joint_hits,self.v765_joint_votes);\n                pnp::println!("P{}/r{} J{}/{}",self.bucket_expected_post_proto as char,self.bucket_expected_post_rot,self.v765_joint_j_a,self.v765_joint_j_s);\n                pnp::println!("DV{:04X} B->REL->UP",self.practical_raw);'''
if old not in t: raise SystemExit('v765 lock UI anchor missing')
t=t.replace(old,new,1)
t=t.replace('pnp::println!("S763 REL40 SHINY PASS");','pnp::println!("S765 REL40 SHINY PASS");',1)

P.write_text(p);T.write_text(t)
print('Applied v7.6.5 joint root selector')
