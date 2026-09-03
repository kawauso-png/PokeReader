#!/usr/bin/env python3
from pathlib import Path
P=Path('reader_core/src/crystal/practical.rs'); T=Path('reader_core/src/crystal/trace.rs'); M=Path('3gx/sources/main.c')
ps=P.read_text(); ts=T.read_text(); ms=M.read_text()

def rep(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'v743 {label}: expected 1, got {n}')
    return s.replace(a,b,1)

# Production evaluator for the experimentally repeatable B76 + START M0 + Resume M14 -> B/r9 actuator.
# Reuse the historical A/r10 -> B/r9 lane-3 prefix (source 0095), and score both the proven route3
# deep family and the generic observed route4 tail.  This is intentionally bucket76-only.
insert='''

/// v7.4.3 experimental production evaluator for B76 + ABS START M0 + RESUME M14.
/// Hardware: M14 -> B/r9 repeated in 0134 and 0139; route3 and route4 have both occurred.
/// Returns Some only when at least one hardware-supported tail family predicts a Gen2 shiny.
pub fn evaluate_m14_b9_dual(state:u16,div:u16,ai:u32,si:u32)->Option<Prediction>{
    if ai==0 || si==0 || !empirical_window_safe(ai,si){return None}
    let l=lane(3); // historical A/r10 -> B/r9 donor, source 0095
    let av=(div>>8)as u8; let sv=div as u8;
    let pre=apply_sums(state,l.full_a[av as usize],l.full_s[sv as usize]);
    let la=av.wrapping_add(l.last_a); let ls=sv.wrapping_add(l.last_s);

    let mut support=0u8; let mut mask=0u8; let mut raw=0u16;
    // route3: require the same weighted support floor used by the production evaluator.
    let mut r3support=0u8; let mut r3raw=0u16;
    for i in 0..5usize{
        let mut st=pre; let mut q=[0u8;3];
        for j in 0..3usize{st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));q[j]=st as u8;}
        if q[0]>=0xc0{continue}
        let v=((q[1]as u16)<<8)|q[2]as u16;
        if shiny(v){r3support=r3support.saturating_add(DEEP_WEIGHT[i]);mask|=1u8<<i;if r3raw==0{r3raw=v;}}
    }
    if r3support>=MIN_SUPPORT_WEIGHT{support=support.saturating_add(r3support);raw=r3raw;}

    // route4: observed on B76/M14 trace 0139.  Use the established 4-call route4 tail family.
    let mut st4=pre; let mut q4=[0u8;4];
    for j in 0..4usize{st4=upd(st4,la.wrapping_add(EMP_R4_A[j]),ls.wrapping_add(EMP_R4_S[j]));q4[j]=st4 as u8;}
    let r4valid=q4[0]>=0xc0;
    let r4raw=((q4[2]as u16)<<8)|q4[3]as u16;
    if r4valid && shiny(r4raw){support=support.saturating_add(4);mask|=0x40;if raw==0{raw=r4raw;}}
    if raw==0{return None}

    let s40=apply_sums(state,l.p40_a[av as usize],l.p40_s[sv as usize]);
    let d40=((av.wrapping_add(l.off40_a)as u16)<<8)|sv.wrapping_add(l.off40_s)as u16;
    let s716=apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]);
    let d716=((av.wrapping_add(l.off716_a)as u16)<<8)|sv.wrapping_add(l.off716_s)as u16;
    let d717=((av.wrapping_add(l.off717_a)as u16)<<8)|sv.wrapping_add(l.off717_s)as u16;
    let s717=upd(s716,(d717>>8)as u8,d717 as u8);
    Some(Prediction{lane_id:3,source:95,support_weight:support,shiny_mask:mask,raw,
        expected40_state:s40,expected40_div:d40,expected716_state:s716,expected716_div:d716,
        expected717_state:s717,expected717_div:d717})
}
'''
anchor='pub fn adaptive_bucket_radius(steps:u32)->u8 {'
pos=ps.index(anchor)
ps=ps[:pos]+insert+ps[pos:]

# Turbo scanner: B76 only, and do not pause until the M14 B/r9 dual-tail evaluator predicts shiny.
old='''        if bucket!=self.sweep_target_bucket { return; }

        self.phase_target_proto=proto0; self.phase_target_rot=rot;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=251;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=add_div_tracker().index().unwrap_or(0) as u32;
        self.practical_live_found_si=sub_div_tracker().index().unwrap_or(0) as u32;
        self.practical_live_scan=false; self.practical_scan_enabled=false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();'''
new='''        if bucket!=76 { return; }
        let ai=add_div_tracker().index().unwrap_or(0) as u32;
        let si=sub_div_tracker().index().unwrap_or(0) as u32;
        let Some(mp)=practical::evaluate_m14_b9_dual(reader.rng_state(),measured_div(),ai,si) else { return; };
        self.practical_raw=mp.raw; self.practical_mask=mp.shiny_mask; self.practical_support=mp.support_weight;
        self.practical_source=mp.source; self.practical_lane=mp.lane_id;
        self.phase_target_proto=proto0; self.phase_target_rot=rot;
        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_lane=251;
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai; self.practical_live_found_si=si;
        self.practical_live_scan=false; self.practical_scan_enabled=false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();'''
ts=rep(ts,old,new,'live M14 shiny gate')

old='''                if proto==b'A' && rot==10 && self.practical_live_found_lane==251 && !self.probe_session
                    && bucket==self.sweep_target_bucket {
                    self.phase_target_proto=proto; self.phase_target_rot=rot;
                    self.practical_live_found_advance=cur;
                    self.practical_live_found_state=reader.rng_state();
                    self.practical_live_found_div=measured_div();
                    self.practical_live_found_tick=pnp::system_tick();
                    self.practical_live_found_ai=add_div_tracker().index().unwrap_or(0) as u32;
                    self.practical_live_found_si=sub_div_tracker().index().unwrap_or(0) as u32;
                    out|=1u32<<27;
                }'''
new='''                if proto==b'A' && rot==10 && self.practical_live_found_lane==251 && !self.probe_session
                    && bucket==76 {
                    let ai=add_div_tracker().index().unwrap_or(0) as u32;
                    let si=sub_div_tracker().index().unwrap_or(0) as u32;
                    if let Some(mp)=practical::evaluate_m14_b9_dual(reader.rng_state(),measured_div(),ai,si){
                        self.practical_raw=mp.raw; self.practical_mask=mp.shiny_mask; self.practical_support=mp.support_weight;
                        self.practical_source=mp.source; self.practical_lane=mp.lane_id;
                        self.phase_target_proto=proto; self.phase_target_rot=rot;
                        self.practical_live_found_advance=cur;
                        self.practical_live_found_state=reader.rng_state();
                        self.practical_live_found_div=measured_div();
                        self.practical_live_found_tick=pnp::system_tick();
                        self.practical_live_found_ai=ai; self.practical_live_found_si=si;
                        out|=1u32<<27;
                    }
                }'''
ts=rep(ts,old,new,'frozen M14 shiny revalidation')

ts=ts.replace('S742 B{} TURBO','S743 M14 TURBO')
ts=ts.replace('S742 B{} SWEEP FOUND','S743 M14 SHINY LOCK')
ts=ts.replace('S742 NEED A EPOCH','S743 NEED A EPOCH')
old='''            pnp::println!("A/r10 TARGET; ABS START M0");
            pnp::println!("RESUME M{:02} X+1 Y-1",pnp::fixed_a_frame().phase_slot & 15);
            pnp::println!("THEN B -> RELEASE -> UP");'''
new='''            pnp::println!("B76 A/r10 START M0 RES M14");
            pnp::println!("PRED {:04X} M{:02X} S{}",self.practical_raw,self.practical_mask,self.practical_support);
            pnp::println!("B -> RELEASE -> UP");'''
ts=rep(ts,old,new,'v743 lock UI')
# Since first format string no longer has {}, remove its stale argument.
ts=ts.replace('pnp::println!("S743 M14 TURBO",self.sweep_target_bucket);','pnp::println!("S743 M14 TURBO");')
ts=ts.replace('pnp::println!("S743 M14 SHINY LOCK",self.sweep_target_bucket);','pnp::println!("S743 M14 SHINY LOCK");')
# Version the sweep diagnostics; actual resume should now always be M14.
ts=ts.replace('SWEEP,V742,','SWEEP,V743,')

# C-side: production fixed Resume M14; remove user phase selector.
ms=ms.replace('if (suicune_phase_slot >= 8U) suicune_phase_slot = 0U;','suicune_phase_slot = 14U;',1)
start=ms.index('// v7.4.2 full absolute resume selector.')
end=ms.index('// v7.2.4 robust diagnostic arm.',start)
ms=ms[:start]+'''// v7.4.3 production: Resume is fixed to absolute M14.\n        suicune_phase_slot = 14U;\n\n        '''+ms[end:]
# Only B76 scan command is production-relevant; keep Y+DOWN and remove Y+UP alternate target.
old='''            if (just_pressed & KEY_DUP)
            {
                suicune_root_lock_active = false;
                suicune_root_lock_ready = false;
                suicune_root_lock_failed = false;
                suicune_wait_up_after_b = false;
                suicune_root_lock_steps = 0;
                suicune_root_lock_last_cell = 0;
                suicune_phase_slot = 9;
                search_suicune_practical_targets();
                svcSleepThread(1000000);
                continue;
            }
'''
ms=rep(ms,old,'','remove B39 command')
# Y+DOWN marker can remain 8 for trace target selection; READY forces M14.

P.write_text(ps); T.write_text(ts); M.write_text(ms)
print('Applied v7.4.3 M14 Turbo Shiny: B76-only, START M0, Resume M14, B/r9 dual route3/route4 shiny gate')
