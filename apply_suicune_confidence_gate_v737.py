#!/usr/bin/env python3
from pathlib import Path

p=Path('reader_core/src/crystal/practical.rs')
t=Path('reader_core/src/crystal/trace.rs')
m=Path('3gx/sources/main.c')
ps=p.read_text(); ts=t.read_text(); ms=m.read_text()

old='''pub struct BucketPrediction {\n    pub prediction: Prediction,\n    pub bucket: u8,\n    pub anchor: u8,\n    pub distance: u8,\n    pub radius: u8,\n    pub post_proto: u8,\n    pub post_rot: u8,\n}'''
new='''pub struct BucketPrediction {\n    pub prediction: Prediction,\n    pub bucket: u8,\n    pub anchor: u8,\n    pub distance: u8,\n    pub radius: u8,\n    pub post_proto: u8,\n    pub post_rot: u8,\n    pub confidence: u8,\n    pub primary_shiny: bool,\n    pub deep_support: u8,\n    pub tracker_safe: bool,\n}'''
assert old in ps
ps=ps.replace(old,new,1)

start=ps.index('pub fn evaluate_adaptive_bucket(')
end=ps.index('\n}', start)+2
oldfn=ps[start:end]
newfn=r'''pub fn evaluate_adaptive_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32,steps:u32)->Option<BucketPrediction> {
    // v7.3.7 restores the empirical tracker-window guard.  The donor sums are
    // only valid when neither rDIV tracker crosses one of the exceptional
    // increment sites during the ~730-advance encounter projection.
    if !empirical_window_safe(ai,si) { return None; }

    let radius=adaptive_bucket_radius(steps);
    let (l,d)=nearest_bucket_lane(bucket);
    if d>radius{return None}
    let av=(div>>8)as u8;let sv=div as u8;
    let pre=apply_sums(state,l.full_a[av as usize],l.full_s[sv as usize]);
    let la=av.wrapping_add(l.last_a);let ls=sv.wrapping_add(l.last_s);

    let mut raw=0u16;
    let mut mask=0u8;
    let mut primary_shiny=false;
    let mut deep_support=0u8;

    // Source-specific deep profile is the strongest single hypothesis because
    // it exactly replays the anchor trace from which this bucket lane came.
    let mut stp=pre;let mut qp=[0u8;3];
    for j in 0..3usize{stp=upd(stp,la.wrapping_add(l.primary_a[j]),ls.wrapping_add(l.primary_s[j]));qp[j]=stp as u8}
    if qp[0]<0xc0{
        let v=((qp[1]as u16)<<8)|qp[2]as u16;
        if shiny(v){primary_shiny=true;raw=v;mask|=0x80;}
    }

    // Global route-3 alternatives retain their historical support weights.
    // v7.3.5/6 incorrectly treated every alternative as weight 1 and locked on
    // any single shiny path.  Require substantial independent support instead.
    for i in 0..5usize{
        let mut st=pre;let mut q=[0u8;3];
        for j in 0..3usize{st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));q[j]=st as u8}
        if q[0]>=0xc0{continue}
        let v=((q[1]as u16)<<8)|q[2]as u16;
        if shiny(v){
            deep_support=deep_support.saturating_add(DEEP_WEIGHT[i]);
            mask|=1u8<<i;
            if raw==0{raw=v}
        }
    }

    // Confidence gate.  Exact/near-anchor buckets can use a source-primary
    // shiny prediction, while extrapolated buckets require weighted consensus.
    // Far nearest-neighbour extrapolation (>16 buckets) is intentionally not
    // auto-armed until hardware data fills the bucket map.
    let confidence:u8;
    let accept=if d<=4{
        confidence=3; // HIGH
        primary_shiny || deep_support>=4
    }else if d<=8{
        confidence=2; // MED
        primary_shiny && deep_support>=2 || deep_support>=6
    }else if d<=16{
        confidence=1; // LOW-MED
        primary_shiny && deep_support>=4 || deep_support>=8
    }else{
        confidence=0;
        false
    };
    if !accept || raw==0{return None}

    let support=deep_support.saturating_add(if primary_shiny{4}else{0});
    let s40=apply_sums(state,l.p40_a[av as usize],l.p40_s[sv as usize]);
    let d40=((av.wrapping_add(l.o40a)as u16)<<8)|sv.wrapping_add(l.o40s)as u16;
    let s716=apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]);
    let d716=((av.wrapping_add(l.o716a)as u16)<<8)|sv.wrapping_add(l.o716s)as u16;
    let d717=((av.wrapping_add(l.o717a)as u16)<<8)|sv.wrapping_add(l.o717s)as u16;
    let s717=upd(s716,(d717>>8)as u8,d717 as u8);
    let pred=Prediction{lane_id:l.id,source:l.source,support_weight:support,shiny_mask:mask,raw,
        expected40_state:s40,expected40_div:d40,expected716_state:s716,expected716_div:d716,
        expected717_state:s717,expected717_div:d717};
    Some(BucketPrediction{prediction:pred,bucket,anchor:l.anchor,distance:d,radius,
        post_proto:l.post_proto,post_rot:l.post_rot,confidence,primary_shiny,deep_support,tracker_safe:true})
}'''
ps=ps[:start]+newfn+ps[end:]

oldcall='evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),self.bucket_scan_steps)'
newcall='evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_tracker_index(),sub_tracker_index(),self.bucket_scan_steps)'
assert oldcall in ts
ts=ts.replace(oldcall,newcall,1)

# Add trace fields for confidence diagnostics.
oldfields='''    bucket_pred_radius: u8,\n    bucket_pred_post_proto: u8,\n    bucket_pred_post_rot: u8,'''
newfields='''    bucket_pred_radius: u8,\n    bucket_pred_post_proto: u8,\n    bucket_pred_post_rot: u8,\n    bucket_pred_confidence: u8,\n    bucket_pred_primary_shiny: bool,\n    bucket_pred_deep_support: u8,\n    bucket_pred_tracker_safe: bool,'''
assert oldfields in ts
ts=ts.replace(oldfields,newfields,1)

oldreset='''            bucket_pred_radius: 0,\n            bucket_pred_post_proto: 0,\n            bucket_pred_post_rot: 0,'''
newreset='''            bucket_pred_radius: 0,\n            bucket_pred_post_proto: 0,\n            bucket_pred_post_rot: 0,\n            bucket_pred_confidence: 0,\n            bucket_pred_primary_shiny: false,\n            bucket_pred_deep_support: 0,\n            bucket_pred_tracker_safe: false,'''
assert oldreset in ts
ts=ts.replace(oldreset,newreset,1)

oldstore='''                    self.bucket_pred_radius = bp.radius;\n                    self.bucket_pred_post_proto = bp.post_proto;\n                    self.bucket_pred_post_rot = bp.post_rot;'''
newstore='''                    self.bucket_pred_radius = bp.radius;\n                    self.bucket_pred_post_proto = bp.post_proto;\n                    self.bucket_pred_post_rot = bp.post_rot;\n                    self.bucket_pred_confidence = bp.confidence;\n                    self.bucket_pred_primary_shiny = bp.primary_shiny;\n                    self.bucket_pred_deep_support = bp.deep_support;\n                    self.bucket_pred_tracker_safe = bp.tracker_safe;'''
assert oldstore in ts
ts=ts.replace(oldstore,newstore,1)

# Version/UI markers.
ts=ts.replace('S736 A-EPOCH SCAN','S737 A-EPOCH SCAN')
ts=ts.replace('S736 PAUSE SHINY SCAN','S737 CONF SHINY SCAN')
ts=ts.replace('S736 SHINY LOCK','S737 SHINY LOCK')
ts=ts.replace('BUCKET736,V736,','BUCKET737,V737,')

# Extend CSV header/row with confidence diagnostics.
oldcsv='''adaptive_bucket,version,bucket,anchor,distance,radius,steps,expected_post_proto,expected_post_rot,actual_post_proto,actual_post_rot,wanted_slot,pred_raw,pred_mask,pred_lane,pred_source'''
newcsv='''adaptive_bucket,version,bucket,anchor,distance,radius,steps,confidence,primary_shiny,deep_support,tracker_safe,expected_post_proto,expected_post_rot,actual_post_proto,actual_post_rot,wanted_slot,pred_raw,pred_mask,pred_lane,pred_source'''
assert oldcsv in ts
ts=ts.replace(oldcsv,newcsv,1)
oldrow='''BUCKET737,V737,{},{},{},{},{},{},{},{},{},1,{:04X},{:02X},{},{}'''
newrow='''BUCKET737,V737,{},{},{},{},{},{},{},{},{},{},{},{},{},1,{:04X},{:02X},{},{}'''
assert oldrow in ts
ts=ts.replace(oldrow,newrow,1)
# Update formatting args for the expanded row.
oldargs='''                self.bucket_pred_bucket,self.bucket_pred_anchor,self.bucket_pred_distance,self.bucket_pred_radius,self.bucket_scan_steps,\n                self.bucket_pred_post_proto as char,self.bucket_pred_post_rot,actual_proto as char,actual_rot,\n                p.raw,p.shiny_mask,p.lane_id,p.source'''
newargs='''                self.bucket_pred_bucket,self.bucket_pred_anchor,self.bucket_pred_distance,self.bucket_pred_radius,self.bucket_scan_steps,\n                self.bucket_pred_confidence,self.bucket_pred_primary_shiny as u8,self.bucket_pred_deep_support,self.bucket_pred_tracker_safe as u8,\n                self.bucket_pred_post_proto as char,self.bucket_pred_post_rot,actual_proto as char,actual_rot,\n                p.raw,p.shiny_mask,p.lane_id,p.source'''
assert oldargs in ts
ts=ts.replace(oldargs,newargs,1)

# Make status string expose confidence/support on lock screen if marker exists.
ts=ts.replace('B{} A{} D{} R{}', 'B{} A{} D{} R{} Q{} S{}')
# There are format call sites corresponding to this marker; patch only the first matching tuple.
oldfmt='''self.bucket_pred_bucket,self.bucket_pred_anchor,self.bucket_pred_distance,self.bucket_pred_radius'''
newfmt='''self.bucket_pred_bucket,self.bucket_pred_anchor,self.bucket_pred_distance,self.bucket_pred_radius,self.bucket_pred_confidence,self.bucket_pred_deep_support'''
if oldfmt in ts: ts=ts.replace(oldfmt,newfmt,1)

# C UI version only; retain v736 watchdog fix and TwoStageArm mechanics.
ms=ms.replace('S736','S737')

p.write_text(ps);t.write_text(ts);m.write_text(ms)
print('applied v7.3.7 confidence gate')
