#!/usr/bin/env python3
from pathlib import Path

T=Path("reader_core/src/crystal/trace.rs")
F=Path("reader_core/src/crystal/frame.rs")
M=Path("reader_core/src/crystal/mod.rs")
L=Path("reader_core/src/lib.rs")
C=Path("3gx/sources/main.c")
H=Path("3gx/includes/pokereader.h")

def rep(src, old, new, label):
    n=src.count(old)
    if n!=1:
        raise SystemExit(f"v795 {label}: expected 1 match, got {n}")
    return src.replace(old,new,1)

def replace_fn(src, sig, new):
    i=src.index(sig)
    b=src.index("{",i)
    depth=0
    j=b
    while j<len(src):
        if src[j]=="{": depth+=1
        elif src[j]=="}":
            depth-=1
            if depth==0:
                return src[:i]+new+src[j+1:]
        j+=1
    raise SystemExit("v795 function end not found: "+sig)

t=T.read_text()

helper=r"""
// v7.9.5 AUDIO DONOR SHINY GATE.
// Read-only comparison at the frozen post-neutral physical-UP Target.
// The fields are exactly the compact AUDIOPRE state used by the offline v7.9.4
// simulator: MusicAddress, LastMusicAddress, low flag bits, NoteDuration,
// NoteDurationModifier, NoteLength, LoopCount, VibratoDelayCount and VibratoRate.
// No RNG/DIV/DV/input memory is written.
#[derive(Clone, Copy, PartialEq, Eq)]
struct V795Sig {
    addr:u16,last:u16,f1:u8,f2:u8,f3:u8,nd:u8,modv:u8,note_len:u8,
    loop_count:u8,vib_count:u8,vib_rate:u8,
}
impl V795Sig {
    const fn new(addr:u16,last:u16,f1:u8,f2:u8,f3:u8,nd:u8,modv:u8,note_len:u8,
        loop_count:u8,vib_count:u8,vib_rate:u8)->Self {
        Self{addr,last,f1,f2,f3,nd,modv,note_len,loop_count,vib_count,vib_rate}
    }
}
#[derive(Clone, Copy)]
struct V795Donor { run:u8,j:i16,post_proto:u8,post_rot:u8,sig:[V795Sig;3] }
impl V795Donor {
    const fn new(run:u8,j:i16,post_proto:u8,post_rot:u8,sig:[V795Sig;3])->Self {
        Self{run,j,post_proto,post_rot,sig}
    }
}
const V795_DONORS:[V795Donor;11]=[
    V795Donor::new(4, -330, b'B', 9, [V795Sig::new(0x73AB,0x737B,3,1,0,0x08,0xF4,0x06,0x00,0x10,0x55), V795Sig::new(0x74C6,0x0000,1,1,0,0x24,0xA8,0x06,0x00,0x00,0x54), V795Sig::new(0x7587,0x755F,3,1,0,0x12,0x30,0x0C,0x00,0x00,0x53)]),
    V795Donor::new(5, 37, b'C', 1, [V795Sig::new(0x72EB,0x737B,1,1,1,0x23,0x00,0x0C,0x00,0x00,0x51), V795Sig::new(0x73FC,0x0000,1,1,1,0x23,0x00,0x06,0x00,0x0A,0x52), V795Sig::new(0x74EF,0x755F,1,1,1,0x23,0x00,0x0C,0x00,0x00,0x55)]),
    V795Donor::new(6, 1376, b'B', 8, [V795Sig::new(0x72EB,0x737B,1,1,0,0x20,0x00,0x0C,0x00,0x00,0x54), V795Sig::new(0x73FC,0x0000,1,1,1,0x20,0x00,0x06,0x00,0x07,0x52), V795Sig::new(0x74EF,0x755F,1,1,1,0x20,0x00,0x0C,0x00,0x00,0x52)]),
    V795Donor::new(7, -27, b'C', 14, [V795Sig::new(0x7339,0x732E,1,1,1,0x04,0xA0,0x06,0x00,0x0C,0x53), V795Sig::new(0x7473,0x0000,1,1,0,0x04,0xA0,0x06,0x00,0x03,0x50), V795Sig::new(0x7576,0x7550,3,1,0,0x04,0xA0,0x0C,0x00,0x0C,0x54)]),
    V795Donor::new(8, 1053, b'A', 1, [V795Sig::new(0x72F8,0x0000,1,1,0,0x43,0x18,0x0C,0x00,0x00,0x52), V795Sig::new(0x741F,0x0000,1,1,0,0x0B,0xB0,0x06,0x00,0x00,0x51), V795Sig::new(0x7509,0x0000,1,1,0,0x0B,0xB0,0x0C,0x00,0x0A,0x54)]),
    V795Donor::new(9, 1186, b'C', 1, [V795Sig::new(0x7318,0x0000,1,1,1,0x0A,0x90,0x06,0x00,0x09,0x51), V795Sig::new(0x7446,0x0000,1,1,0,0x0A,0x90,0x06,0x00,0x09,0x54), V795Sig::new(0x7535,0x0000,1,1,0,0x0A,0x90,0x0C,0x00,0x09,0x54)]),
    V795Donor::new(10, 199, b'C', 3, [V795Sig::new(0x73AA,0x737B,3,1,0,0x02,0xB8,0x06,0x00,0x0A,0x55), V795Sig::new(0x74C6,0x0000,1,1,1,0x27,0xA8,0x06,0x00,0x01,0x50), V795Sig::new(0x7587,0x755F,3,1,0,0x15,0x30,0x0C,0x00,0x01,0x55)]),
    V795Donor::new(11, 32, b'B', 8, [V795Sig::new(0x72F7,0x0000,1,1,0,0x4C,0xC0,0x0C,0x00,0x00,0x52), V795Sig::new(0x741D,0x0000,1,1,1,0x02,0xE0,0x06,0x00,0x0A,0x50), V795Sig::new(0x7506,0x0000,1,1,1,0x4C,0xC0,0x0C,0x00,0x01,0x51)]),
    V795Donor::new(12, 29, b'A', 1, [V795Sig::new(0x731A,0x0000,1,1,1,0x07,0x08,0x06,0x00,0x05,0x51), V795Sig::new(0x7447,0x0000,1,1,0,0x07,0x08,0x06,0x00,0x05,0x54), V795Sig::new(0x7536,0x0000,1,1,0,0x07,0x08,0x0C,0x00,0x05,0x54)]),
    V795Donor::new(13, 861, b'A', 1, [V795Sig::new(0x72F8,0x0000,1,1,1,0x59,0x18,0x0C,0x00,0x0D,0x55), V795Sig::new(0x741F,0x0000,1,1,1,0x21,0xB0,0x06,0x00,0x0D,0x54), V795Sig::new(0x7508,0x0000,1,1,0,0x0F,0x38,0x0C,0x00,0x0D,0x55)]),
    V795Donor::new(14, -544, b'D', 1, [V795Sig::new(0x7341,0x732E,1,1,1,0x09,0x08,0x06,0x00,0x10,0x53), V795Sig::new(0x7478,0x0000,1,1,1,0x1B,0x80,0x06,0x00,0x07,0x55), V795Sig::new(0x757A,0x7550,3,1,0,0x09,0x08,0x0C,0x00,0x07,0x54)]),
];
static mut V795_LAST_GATE_WORD:u32=0;

fn v795_u16(a:u32)->u16 {
    (gb_mem::read_u8(a) as u16) | ((gb_mem::read_u8(a+1) as u16)<<8)
}
fn v795_read_sig(ch:usize)->V795Sig {
    let b=0x0000c101u32 + (ch as u32)*0x32;
    V795Sig {
        addr:v795_u16(b+6), last:v795_u16(b+8),
        f1:gb_mem::read_u8(b+3)&7, f2:gb_mem::read_u8(b+4)&7, f3:gb_mem::read_u8(b+5)&3,
        nd:gb_mem::read_u8(b+0x15), modv:gb_mem::read_u8(b+0x16),
        note_len:gb_mem::read_u8(b+0x2d), loop_count:gb_mem::read_u8(b+0x18),
        vib_count:gb_mem::read_u8(b+0x1d), vib_rate:gb_mem::read_u8(b+0x20),
    }
}
"""
t=rep(t,"impl Trace {\n",helper+"\nimpl Trace {\n","trace helper insert")

method=r"""    pub fn audio_donor_gate_v795(&mut self)->u32 {
        let live=[v795_read_sig(0),v795_read_sig(1),v795_read_sig(2)];
        let mut word=0u32;
        for d in V795_DONORS.iter() {
            if d.sig != live { continue; }
            // bit30 = exact AUDIOPRE donor matched.
            word=(1u32<<30)|(d.run as u32)|((d.post_rot as u32)<<8)|((d.post_proto as u32)<<16);
            // The PRE shiny model and measured audio transport must agree on POST.
            // Only then may the user be asked for a physical UP.
            if d.post_proto==self.bucket_expected_post_proto
                && d.post_rot==self.bucket_expected_post_rot
            {
                word|=1u32<<31;
            }
            break;
        }
        unsafe { V795_LAST_GATE_WORD=word; }
        word
    }

"""
t=rep(t,"impl Trace {\n","impl Trace {\n"+method,"trace donor method")

new_monitor=r"""    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        // v7.9.5: production PRE shiny selector restored on the modern
        // A/r10 bucket76 -> neutral3F -> A/r13 physical-UP flow.
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid
        { return; }

        let cur=rng_advance();
        if cur==self.practical_live_last_advance { return; }
        self.practical_live_last_advance=cur;
        self.practical_live_checked=self.practical_live_checked.saturating_add(1);

        let r=latest_pre_vblank_ring();
        let n=(r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n!=PRE_VBLANK_RING_LEN { return; }
        let(last,_)=pre_ring_sample(&r,n-1);
        let lag=cur.wrapping_sub(last);
        let(proto0,mut rot,best,second,ok)=classify_pre_ring(&r);
        self.phase_best_score=best; self.phase_second_score=second; self.phase_consecutive=ok;
        self.phase_now_proto=proto0; self.phase_now_rot=rot; self.phase_now_lag=lag.min(255)as u8;
        if lag==1 { rot=rot.wrapping_add(1)&15; }
        if lag!=0 || !ok || best!=0 || proto0!=b'A' || rot!=10 { return; }

        let(_,p0)=pre_ring_sample(&r,0);
        let pd=p0.wrapping_sub(0x0035)&0x3fff;
        if (pd&0x003f)!=0 { return; }
        let bucket=((pd>>6)&0xff)as u8;
        self.bucket_current=bucket;
        if bucket!=76 { return; }

        let Some(ai0)=add_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1); return;
        };
        let Some(si0)=sub_div_tracker().index() else {
            self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1); return;
        };
        let ai=(ai0 as u32)&0x3fff; let si=(si0 as u32)&0x3fff;
        self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);

        let Some(bp)=practical::evaluate_weighted_bucket_inverse(
            76,reader.rng_state(),measured_div(),ai,si
        ) else { return; };

        self.phase_target_proto=b'A'; self.phase_target_rot=10;
        self.bucket_model_active=true; self.bucket_current=76;
        self.bucket_anchor=bp.anchor; self.bucket_distance=bp.distance; self.bucket_radius=bp.radius;
        self.bucket_expected_post_proto=bp.post_proto;
        self.bucket_expected_post_rot=bp.post_rot;
        self.multipre_score=bp.prediction.support_weight;
        self.multipre_branches=bp.prediction.shiny_mask.count_ones().min(255) as u8;

        self.practical_live_found_advance=cur;
        self.practical_live_found_state=reader.rng_state();
        self.practical_live_found_div=measured_div();
        self.practical_live_found_tick=pnp::system_tick();
        self.practical_live_found_ai=ai; self.practical_live_found_si=si;
        self.bind_practical_prediction(bp.prediction);
        self.practical_live_found_lane=253;
        self.practical_empirical=false;
        self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);
        self.practical_live_scan=false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }"""
t=replace_fn(t,"    fn live_root_monitor(&mut self, reader: &Gen2Reader)",new_monitor)

t=t.replace('S786 NEUTRAL SCAN A/r10 B76','S795 SHINY+DONOR SCAN')
t=t.replace('S784 MULTI-PRE CAND','S795 PRE-SHINY ROOT')
t=t.replace('pnp::println!("B -> RELEASE -> UP");',
            'pnp::println!("B -> 3F DONOR CHECK");\n                pnp::println!("STAYS PAUSED = HOLD UP");')
T.write_text(t)

f=F.read_text()
insert=r"""
pub fn audio_donor_gate() -> u32 {
    let state=unsafe { get_state() };
    state.trace.audio_donor_gate_v795()
}

"""
f=rep(f,"pub fn run_frame() {",insert+"pub fn run_frame() {","frame export")
F.write_text(f)

m=M.read_text()
m=rep(m,"pub use frame::{arm_suicune_probe, run_frame};",
      "pub use frame::{arm_suicune_probe, audio_donor_gate, run_frame};","mod export")
M.write_text(m)

l=L.read_text()
ffi=r"""
#[no_mangle]
pub extern "C" fn suicune_audio_donor_gate() -> u32 {
    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {
        crystal::audio_donor_gate()
    } else {
        0
    }
}

"""
l=rep(l,'#[no_mangle]\npub extern "C" fn run_frame() {',ffi+'#[no_mangle]\npub extern "C" fn run_frame() {',"lib ffi")
L.write_text(l)

h=H.read_text()
h=rep(h,"void arm_suicune_probe();","void arm_suicune_probe();\nu32 suicune_audio_donor_gate();","header ffi")
H.write_text(h)

c=C.read_text()
old="""                suicune_neutral_probe_pending = false;
                arm_suicune_probe();
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;"""
new="""                suicune_neutral_probe_pending = false;

                // v7.9.5 physical-UP labor gate.  We are frozen at the exact
                // post-neutral Target (A/r13 in the measured corpus), so these
                // WRAM reads cannot consume guest cycles.  No match, or a donor
                // whose measured POST disagrees with the PRE shiny hypothesis,
                // is rejected before any physical UP is requested.
                u32 donor_gate = suicune_audio_donor_gate();
                if ((donor_gate & 0x80000000U) == 0)
                {
                    suicune_live_pass_ready = false;
                    suicune_wait_up_after_b = false;
                    fixed_armed = false;
                    fixed_frames_remaining = 0;
                    fixed_run_pending = false;
                    suicune_auto_resume_pending = false;
                    suicune_phase_lock_active = false;
                    suicune_start_phase_lock_active = false;
                    suicune_neutral_probe_remaining = 0;
                    suicune_neutral_probe_executed = 0;
                    suicune_neutral_probe_pending = false;
                    // Return immediately to the rolling shiny-root scan.
                    search_suicune_practical_targets();
                    is_paused = false;
                    break;
                }

                arm_suicune_probe();
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;"""
c=rep(c,old,new,"neutral donor gate")
C.write_text(c)

print("Applied v7.9.5 donor-gated shiny hunt: PRE shiny root -> neutral3F -> exact AUDIOPRE donor+POST gate -> physical UP only on match")
