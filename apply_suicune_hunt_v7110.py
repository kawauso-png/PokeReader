#!/usr/bin/env python3
"""Apply ONLY after generated v7100. PRE-only experimental hunt, not a proven selector."""
from pathlib import Path
import base64,json,struct,zlib,hashlib
ROOT=Path('.')
D=json.loads(zlib.decompress(base64.b85decode((ROOT/'hunt_v7110_donors.b85').read_text().strip())))
def sums(phases):
    hist_a=[0]*16384;hist_s=[0]*16384
    for aa,ss in phases:hist_a[aa]+=1;hist_s[ss]+=1
    counts_a=[sum(hist_a[x::64]) for x in range(64)]
    counts_s=[sum(hist_s[x::64]) for x in range(64)]
    value=sum((aa>>6)+256*(ss>>6) for aa,ss in phases)&65535
    arr=[]
    for k in range(16384):
        arr.append(value)
        ix=(63-k)&63;wrap=(16383-k)&16383
        value=(value+counts_a[ix]-256*hist_a[wrap]+256*counts_s[ix])&65535
    assert value==arr[0]
    for k in [0,1,4,63,64,80,127,255,512,1234,4095,8192,16383]:
        assert arr[k]==sum((((aa+k)&16383)>>6)+256*(((ss+k)&16383)>>6) for aa,ss in phases)&65535
    return arr
blob=bytearray();manifest=[]
for d in D:
    packed=zlib.decompress(base64.b85decode(d['phase_blob']));ph=[];last=0
    for delta,gap in struct.iter_unpack('<hB',packed):
        last=(last+1172+delta)&16383;ph.append((last,(last+gap)&16383))
    j=d['jump']-1;before=sums(ph[:j]);after=sums(ph[j:])
    blob+=struct.pack('<4H',d['c'],d['root_ap4'],*ph[-1])
    blob+=struct.pack('<256H',*[before[k*64] for k in range(256)])
    blob+=struct.pack('<16384H',*after)
    manifest.append({k:d[k] for k in ('name','sha256','c','jump','route')})
assert len(blob)==332880
p=ROOT/'reader_core/src/crystal';(p/'hunt_v7110.bin').write_bytes(blob)
(p/'hunt_v7110.rs').write_text((ROOT/'hunt_v7110.rs').read_text())
(ROOT/'hunt_v7110_manifest.json').write_text(json.dumps({'mode':'experimental workload-adjusted full-path ensemble','score_is_probability':False,'donors':manifest,'table_sha256':hashlib.sha256(blob).hexdigest()},indent=2))
s=(p/'trace.rs').read_text()
assert 'S1CAL,V7100' in s and 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in s
assert 'V7110_HUNT' not in s
extra=r'''
#[path="hunt_v7110.rs"]
mod hunt_v7110;
static mut V7110_HUNT:bool=false;
static mut V7110_LAST:u32=u32::MAX;
static mut V7110_EVALS:u32=0;
static mut V7110_MISSES:u32=0;
static mut V7110_FROZEN:bool=false;
static mut V7110_STATE:u16=0;
static mut V7110_PHASE:u16=0;
static mut V7110_CYCLES:u16=0;
static mut V7110_SCORE:hunt_v7110::Score=hunt_v7110::Score::EMPTY;
static mut V7110_BITS:[u8;8192]=[0;8192];
unsafe fn v7110_pre_check(reader:&Gen2Reader)->bool {
    let cur=rng_advance();
    if V7110_LAST==cur {return hunt_v7110::ready(V7110_SCORE);}
    V7110_LAST=cur;V7110_SCORE=hunt_v7110::Score::EMPTY;V7110_EVALS=V7110_EVALS.saturating_add(1);
    let phase=direct_phase_m((measured_div()>>8) as u8,adiv_subtick());
    if phase&63!=53 {return false;}
    for i in 0..V792_AUDIO_PRE_LEN {V792_AUDIO_PRE[i]=gb_mem::read_u8(V792_AUDIO_PRE_BASE+i as u32);}
    V792_AUDIO_PRE_VALID=true;V792_AUDIO_PRE_TARGET=cur;
    v796_predict_j_from_audiopre();
    if !V796_JPRED_VALID {V7110_MISSES=V7110_MISSES.saturating_add(1);return false;}
    V7110_STATE=reader.rng_state();V7110_PHASE=phase;V7110_CYCLES=V796_JPRED_C28;
    V7110_SCORE=hunt_v7110::evaluate(V7110_STATE,phase,V7110_CYCLES,&mut *core::ptr::addr_of_mut!(V7110_BITS));
    hunt_v7110::ready(V7110_SCORE)
}
'''
s=extra+s
needle='        self.reset_scan_epoch();'
pos=s.index(needle,s.index('pub fn start_practical_scan'))
s=s[:pos]+s[pos:].replace(needle,'        self.stop(); self.reset(); self.probe_session=false; self.probe_active=false;\n'+needle+'\n        unsafe {V7110_HUNT=true;V7110_LAST=u32::MAX;V7110_EVALS=0;V7110_MISSES=0;V7110_FROZEN=false;V7110_SCORE=hunt_v7110::Score::EMPTY;}\n',1)
s=s.replace('        if bucket != 76 { return; }','        // v7110 scans all A/r10 buckets; PRE-only selection follows 3 neutral frames.',1)
s=s.replace('        self.bucket_current = 76;\n        self.bucket_anchor = 76;','        self.bucket_current = bucket;\n        self.bucket_anchor = bucket;',1)
s=s.replace('&& bucket_valid && bucket == 76;','&& bucket_valid;',1)
s=s.replace('                    self.bucket_current = 76;','                    self.bucket_current = bucket;',1)
needle='        out\n    }\n\n    pub fn status_line';assert needle in s
s=s.replace(needle,'''        if phase_probe && count==PRE_VBLANK_RING_LEN && consecutive && best==0
            && proto==b'A' && rot==13 {
            unsafe {if V7110_HUNT && v7110_pre_check(reader) {out|=1u32<<25;}}
        }
        out
    }

    pub fn status_line''',1)
needle='        deep_log_clear();\n        self.early_rel26_count = 0;';assert needle in s
s=s.replace(needle,'''        deep_log_clear();
        unsafe {
            V798_CAL_LAST_TARGET=u32::MAX;V7100_LAST_TARGET=u32::MAX;
            V790_CPU_CTX_VALID=false;V790_CPU_CTX_TARGET=u32::MAX;
            V7110_FROZEN=V7110_HUNT && V7110_LAST==rng_advance() && hunt_v7110::ready(V7110_SCORE);
        }
        self.early_rel26_count = 0;''',1)
needle='        let em = pnp::early_control_metrics();'
save=r'''        unsafe {
            if V7110_FROZEN {
                line.clear();
                let sc=V7110_SCORE;
                let _=write!(line,"hunt,version,target,state,phase,cycles28,donor_support,score,total_weight,unique_raws,first_shiny,evals,table_misses,guaranteed\nHUNT,V7110,{},{:04X},{:04X},{},{},{},{},{},{:04X},{},{},0\n\n",V7110_LAST,V7110_STATE,V7110_PHASE,V7110_CYCLES,sc.support,sc.score,sc.total,sc.unique,sc.first,V7110_EVALS,V7110_MISSES);
                pnp::trace_file_write(line.as_bytes());
                line.clear();let _=write!(line,"hunt_candidate,version,raw\n");pnp::trace_file_write(line.as_bytes());
                for raw in 0..65536usize {
                    if V7110_BITS[raw>>3]&(1u8<<(raw&7))!=0 {
                        line.clear();let _=write!(line,"HUNTDV,V7110,{:04X}\n",raw);pnp::trace_file_write(line.as_bytes());
                    }
                }
                line.clear();let _=write!(line,"\n");pnp::trace_file_write(line.as_bytes());
            }
        }
'''
assert needle in s;s=s.replace(needle,save+needle,1)
needle='    pub fn draw_rng_status(&self) {\n';assert needle in s
ui=r'''        unsafe {
            if V7110_HUNT && (!self.probe_session || self.probe_active) {
                if self.probe_session && V7110_FROZEN {
                    let sc=V7110_SCORE;
                    pnp::println!("H7110 CANDIDATE - NOT CERTAIN");
                    pnp::println!("SUP{} SCORE{} DV{:04X}",sc.support,sc.score,sc.first);
                    pnp::println!("PHYSICAL UP ONLY");
                    pnp::println!("EXACT2 -> RELEASE -> M14");
                    pnp::println!("NATIVE RESULT + AUTO SAVE");
                } else {
                    pnp::println!("H7110 EMPIRICAL HUNT");
                    pnp::println!("AUTO SCAN - RELEASE ALL KEYS");
                    pnp::println!("ADV{} EVAL{} MISS{}",rng_advance(),V7110_EVALS,V7110_MISSES);
                    pnp::println!("SUP{} SCORE{}",V7110_SCORE.support,V7110_SCORE.score);
                    pnp::println!("WAIT FOR CANDIDATE / UP");
                }
                return;
            }
        }
'''
s=s.replace(needle,needle+ui,1)
s=s.replace('STALLPHASE,V7100,','STALLPHASE,V7110,')
(p/'trace.rs').write_text(s)
cp=ROOT/'3gx/sources/main.c';c=cp.read_text()
needle='static bool suicune_root_lock_active = false;';assert needle in c
c=c.replace(needle,'static bool suicune_hunt_v7110 = false;\n'+needle,1)
c=c.replace('if (!suicune_auto_resume_pending && !fixed_run_pending && fixed_frames_remaining == 0)','if (!suicune_auto_resume_pending && !fixed_run_pending && fixed_frames_remaining == 0 && !suicune_wait_up_after_b)',1)
needle='''                    if (suicune_phase_slot >= 8U) suicune_phase_slot = 0U;
                    continue;''';assert needle in c
c=c.replace(needle,'''                    if (suicune_phase_slot >= 8U) suicune_phase_slot = 0U;
                    if (suicune_hunt_v7110) {
                        suicune_root_lock_ready=false;
                        suicune_wait_up_after_b=true;
                        suicune_neutral_probe_frames=3;
                        suicune_neutral_probe_remaining=3;
                        suicune_neutral_probe_executed=0;
                        suicune_neutral_probe_pending=true;
                        suicune_live_pass_ready=false;
                        suicune_start_phase_slot=3;
                    }
                    continue;''',1)
needle='''                suicune_neutral_probe_pending = false;
                arm_suicune_probe();''';assert needle in c
c=c.replace(needle,'''                suicune_neutral_probe_pending = false;
                if (suicune_hunt_v7110 && !(suicune_control_pause_cell() & 0x02000000U)) {
                    suicune_wait_up_after_b=false;
                    suicune_root_lock_ready=false;
                    suicune_root_lock_active=true;
                    suicune_live_pass_ready=false;
                    continue;
                }
                arm_suicune_probe();''',1)
needle='''            // Stage3 current-root live scan start.
            if (just_pressed & KEY_DDOWN)
            {''';assert needle in c
c=c.replace(needle,needle+'\n                suicune_hunt_v7110=true;',1)
cp.write_text(c)
assert 'const u32 wanted = 14U' in c
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in s
assert 'write_u8' not in extra and 'write_u16' not in extra and 'KEY_DUP' not in extra
print('V7110 applied; 10 current-build donors; shift-sum assertions passed; no RNG/DIV/DV/save writes added.')
