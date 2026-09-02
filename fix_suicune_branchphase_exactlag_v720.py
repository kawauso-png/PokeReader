#!/usr/bin/env python3
from pathlib import Path

P=Path('reader_core/src/crystal/trace.rs')
s=P.read_text()

def rep(old,new,label):
    global s
    n=s.count(old)
    if n!=1:
        raise SystemExit(f'v720 exactlag {label}: expected 1 match, got {n}')
    s=s.replace(old,new,1)

rep(
'''    fn live_pre_cell(&self)->Option<(u8,u8)>{let r=latest_pre_vblank_ring();let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);if n!=PRE_VBLANK_RING_LEN{return None}let(last,_)=pre_ring_sample(&r,n-1);let lag=rng_advance().wrapping_sub(last);if lag>1{return None}let(p,mut rot,best,_,ok)=classify_pre_ring(&r);if !ok||best!=0{return None}if lag==1{rot=rot.wrapping_add(1)&15}Some((p,rot))}
    fn live_practical_lane(&self)->Option<u8>{let(p,r)=self.live_pre_cell()?;practical::lane_for_pre(p,r)}''',
'''    fn live_pre_cell(&self)->Option<(u8,u8)>{let r=latest_pre_vblank_ring();let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);if n!=PRE_VBLANK_RING_LEN{return None}let(last,_)=pre_ring_sample(&r,n-1);let lag=rng_advance().wrapping_sub(last);if lag>1{return None}let(p,mut rot,best,_,ok)=classify_pre_ring(&r);if !ok||best!=0{return None}if lag==1{rot=rot.wrapping_add(1)&15}Some((p,rot))}
    fn live_pre_cell_v720(&self)->Option<(u8,u8,u32)>{let r=latest_pre_vblank_ring();let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);if n!=PRE_VBLANK_RING_LEN{return None}let(last,_)=pre_ring_sample(&r,n-1);let lag=rng_advance().wrapping_sub(last);if lag>1{return None}let(p,mut rot,best,_,ok)=classify_pre_ring(&r);if !ok||best!=0{return None}if lag==1{rot=rot.wrapping_add(1)&15}Some((p,rot,lag))}
    fn live_practical_lane(&self)->Option<u8>{let(p,r)=self.live_pre_cell()?;practical::lane_for_pre(p,r)}''',
'add lag-aware PRE classifier')

rep(
'''        let Some((proto, rot)) = self.live_pre_cell() else {
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        };''',
'''        let Some((proto, rot, lag)) = self.live_pre_cell_v720() else {
            self.practical_live_no_lane = self.practical_live_no_lane.saturating_add(1);
            return;
        };
        if lag != 0 {
            return;
        }''',
'require lag-zero target')

P.write_text(s)
print('Applied v7.2.0 exact-lag probe guard: BRPHASE endpoint must be the current root (lag=0)')
