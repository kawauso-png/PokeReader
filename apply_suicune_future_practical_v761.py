from pathlib import Path
P=Path('reader_core/src/crystal/practical.rs')
p=P.read_text()
old='''    // Experimental first-pass gate: do not stop for a one-off weak tail.\n    // The rel40 rebind remains authoritative after Exact2F.\n    if score<12{return None}\n'''
new='''    // v7.6.1: this evaluator is a ranking primitive. Keep every nonzero\n    // shiny hypothesis and let the future-window selector choose the best one.\n    // MODEL SCORE is not a calibrated physical probability.\n'''
if old not in p: raise SystemExit('v760 score gate anchor missing')
p=p.replace(old,new,1)
if 'pub fn select_future_weighted_a10' in p: raise SystemExit('v761 already applied')
p += r'''

// v7.6.1 Direct Future ADV Selector.
// Start only from an observed exact A/r10 root. DivTracker::index() points to
// the next normal 0x12/0x13 increment. For each future ADV: advance DIV first,
// then apply that DIV to the Gen2 RNG state. A/r10 recurs every +16 ADV and
// bucket advances +37 mod256. No game memory is written.
#[derive(Clone,Copy)]
pub struct FutureBucketPrediction {
    pub bucket_prediction: BucketPrediction,
    pub delta_adv: u32,
    pub target_state: u16,
    pub target_div: u16,
    pub target_ai: u32,
    pub target_si: u32,
    pub profile_count: u8,
    pub rank: u32,
}
pub const FUTURE_ROOTS_V761:u16=256;

pub fn select_future_weighted_a10(bucket0:u8,state0:u16,div0:u16,ai0:u32,si0:u32)->Option<FutureBucketPrediction>{
    if ai0==0||si0==0{return None}
    let mut st=state0;
    let mut av=(div0>>8)as u8;
    let mut sv=div0 as u8;
    let mut ai=ai0&0x3fff;
    let mut si=si0&0x3fff;
    let mut bucket=bucket0;
    let mut best:Option<FutureBucketPrediction>=None;
    for root in 1..=FUTURE_ROOTS_V761 as u32{
        for _ in 0..16{
            av=av.wrapping_add(normal_inc_full(ai));
            sv=sv.wrapping_add(normal_inc_full(si));
            ai=ai.wrapping_add(1)&0x3fff;
            si=si.wrapping_add(1)&0x3fff;
            st=upd(st,av,sv);
        }
        bucket=bucket.wrapping_add(37);
        let div=((av as u16)<<8)|sv as u16;
        let Some(bp)=evaluate_weighted_bucket(bucket,st,div,ai,si)else{continue};
        let profiles=bp.prediction.shiny_mask.count_ones()as u8;
        let rank=((bp.prediction.support_weight as u32)<<16)|((profiles as u32)<<8)|(255u32.saturating_sub(bp.distance as u32));
        let take=match best{None=>true,Some(x)=>rank>x.rank||(rank==x.rank&&root*16<x.delta_adv)};
        if take{best=Some(FutureBucketPrediction{bucket_prediction:bp,delta_adv:root*16,target_state:st,target_div:div,target_ai:ai,target_si:si,profile_count:profiles,rank})}
    }
    best
}

pub fn bucket_post_known(proto:u8,rot:u8)->bool{
    BUCKET_LANES.iter().any(|l|l.post_proto==proto&&l.post_rot==rot)
}

// rel40 actual-POST rebind for the weighted bucket model. The measured rel40
// state/DIV becomes the new anchor. Some is returned only if a retained deep
// hypothesis is still shiny; known POST + None can therefore abort early.
pub fn evaluate_bucket_post_weighted(proto:u8,rot:u8,state40:u16,div40:u16)->Option<Prediction>{
    let mut total=0u32;let mut shiny_weight=0u32;let mut mask=0u8;
    let mut best_w=0u32;let mut best_raw=0u16;let mut best_lane:Option<&BucketLane>=None;
    let mut bs716=0u16;let mut bd716=0u16;let mut bs717=0u16;let mut bd717=0u16;
    for l in BUCKET_LANES.iter().filter(|l|l.post_proto==proto&&l.post_rot==rot){
        let a40=(div40>>8)as u8;let s40=div40 as u8;
        let av0=a40.wrapping_sub(l.o40a);let sv0=s40.wrapping_sub(l.o40s);
        let sa716=l.p716_a[av0 as usize].wrapping_sub(l.p40_a[av0 as usize]);
        let ss716=l.p716_s[sv0 as usize].wrapping_sub(l.p40_s[sv0 as usize]);
        let s716=apply_sums(state40,sa716,ss716);
        let a716=av0.wrapping_add(l.o716a);let x716=sv0.wrapping_add(l.o716s);let d716=((a716 as u16)<<8)|x716 as u16;
        let a717=av0.wrapping_add(l.o717a);let x717=sv0.wrapping_add(l.o717s);let d717=((a717 as u16)<<8)|x717 as u16;let s717=upd(s716,a717,x717);
        let safull=l.full_a[av0 as usize].wrapping_sub(l.p40_a[av0 as usize]);
        let ssfull=l.full_s[sv0 as usize].wrapping_sub(l.p40_s[sv0 as usize]);
        let pre=apply_sums(state40,safull,ssfull);
        let la=av0.wrapping_add(l.last_a);let ls=sv0.wrapping_add(l.last_s);
        for i in 0..W760_A.len(){
            let w=W760_W[i]as u32;total=total.saturating_add(w);
            let mut st=pre;let mut q=[0u8;3];
            for j in 0..3usize{st=upd(st,la.wrapping_add(W760_A[i][j]),ls.wrapping_add(W760_S[i][j]));q[j]=st as u8}
            if q[0]>=0xc0{continue}
            let raw=((q[1]as u16)<<8)|q[2]as u16;
            if shiny(raw){shiny_weight=shiny_weight.saturating_add(w);mask|=1u8<<i;if w>best_w{best_w=w;best_raw=raw;best_lane=Some(l);bs716=s716;bd716=d716;bs717=s717;bd717=d717}}
        }
        if !w760_primary_is_listed(l.primary_a,l.primary_s){
            let w=2u32;total=total.saturating_add(w);let mut st=pre;let mut q=[0u8;3];
            for j in 0..3usize{st=upd(st,la.wrapping_add(l.primary_a[j]),ls.wrapping_add(l.primary_s[j]));q[j]=st as u8}
            if q[0]<0xc0{let raw=((q[1]as u16)<<8)|q[2]as u16;if shiny(raw){shiny_weight=shiny_weight.saturating_add(w);if w>best_w{best_w=w;best_raw=raw;best_lane=Some(l);bs716=s716;bd716=d716;bs717=s717;bd717=d717}}}
        }
    }
    let l=best_lane?;
    if total==0||shiny_weight==0{return None}
    let score=((shiny_weight.saturating_mul(100)+total/2)/total).min(100)as u8;
    Some(Prediction{lane_id:l.id,source:l.source,support_weight:score,shiny_mask:mask,raw:best_raw,expected40_state:state40,expected40_div:div40,expected716_state:bs716,expected716_div:bd716,expected717_state:bs717,expected717_div:bd717})
}
'''
P.write_text(p)
