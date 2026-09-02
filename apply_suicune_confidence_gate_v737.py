#!/usr/bin/env python3
from pathlib import Path

p=Path('reader_core/src/crystal/practical.rs')
t=Path('reader_core/src/crystal/trace.rs')
m=Path('3gx/sources/main.c')
ps=p.read_text(); ts=t.read_text(); ms=m.read_text()

# Keep BucketPrediction ABI compact; confidence is enforced before Some().
start=ps.index('pub fn evaluate_adaptive_bucket(')
end=ps.index('\n}', start)+2
newfn=r'''pub fn evaluate_adaptive_bucket(bucket:u8,state:u16,div:u16,ai:u32,si:u32,steps:u32)->Option<BucketPrediction> {
    // v7.3.7: restore the empirical tracker-window guard that v735/v736
    // accidentally bypassed.  Index 0 is treated conservatively as unavailable.
    if ai==0 || si==0 || !empirical_window_safe(ai,si) { return None; }

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

    // Strongest single hypothesis: the exact deep profile of this bucket's
    // hardware donor trace.
    let mut stp=pre;let mut qp=[0u8;3];
    for j in 0..3usize{
        stp=upd(stp,la.wrapping_add(l.primary_a[j]),ls.wrapping_add(l.primary_s[j]));
        qp[j]=stp as u8;
    }
    if qp[0]<0xc0{
        let v=((qp[1]as u16)<<8)|qp[2]as u16;
        if shiny(v){ primary_shiny=true; raw=v; mask|=0x80; }
    }

    // Alternative route3 profiles use the same historical evidence weights as
    // the proven/empirical evaluators.  v735/v736 incorrectly counted every
    // alternative as weight 1 and accepted any single shiny alternative.
    for i in 0..5usize{
        let mut st=pre;let mut q=[0u8;3];
        for j in 0..3usize{
            st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));
            q[j]=st as u8;
        }
        if q[0]>=0xc0{continue}
        let v=((q[1]as u16)<<8)|q[2]as u16;
        if shiny(v){
            deep_support=deep_support.saturating_add(DEEP_WEIGHT[i]);
            mask|=1u8<<i;
            if raw==0{raw=v}
        }
    }

    // Distance-aware confidence gate.  The five anchors are each one hardware
    // observation; nearest-neighbour extrapolation is not trusted beyond 16
    // buckets.  Near anchors may use the exact donor-primary prediction, while
    // farther buckets require increasingly strong weighted multi-profile support.
    let accept=if d<=4{
        primary_shiny || deep_support>=4
    }else if d<=8{
        (primary_shiny && deep_support>=2) || deep_support>=6
    }else if d<=16{
        (primary_shiny && deep_support>=4) || deep_support>=8
    }else{
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
        post_proto:l.post_proto,post_rot:l.post_rot})
}'''
ps=ps[:start]+newfn+ps[end:]

oldcall='practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),self.bucket_scan_steps)'
newcall='practical::evaluate_adaptive_bucket(bucket,reader.rng_state(),measured_div(),add_div_tracker().index().unwrap_or(0) as u32,sub_div_tracker().index().unwrap_or(0) as u32,self.bucket_scan_steps)'
assert oldcall in ts, 'adaptive call anchor missing'
ts=ts.replace(oldcall,newcall,1)

# Version/UI/CSV markers; diagnostics already expose distance, radius, mask,
# support and actual POST, so avoid enlarging the hot Trace struct.
ts=ts.replace('S736 A-EPOCH SCAN','S737 A-EPOCH SCAN')
ts=ts.replace('S736 PAUSE SHINY SCAN','S737 CONF SHINY SCAN')
ts=ts.replace('S736 SHINY LOCK','S737 SHINY LOCK')
ts=ts.replace('BUCKET736,V736,','BUCKET737,V737,')
ms=ms.replace('S736','S737')

p.write_text(ps);t.write_text(ts);m.write_text(ms)
print('applied v7.3.7 confidence gate')
