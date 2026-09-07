#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
F = Path('reader_core/src/crystal/frame.rs')
L = Path('reader_core/src/lib.rs')
H = Path('3gx/includes/pokereader.h')
C = Path('3gx/sources/main.c')

t=T.read_text(); f=F.read_text(); l=L.read_text(); h=H.read_text(); c=C.read_text()

def rep(src, old, new, label):
    n=src.count(old)
    if n != 1:
        raise SystemExit(f'v795 {label}: expected 1 match, got {n}')
    return src.replace(old,new,1)

def replace_fn(src, sig, new):
    i=src.index(sig)
    b=src.index('{', i)
    depth=0
    j=b
    while j < len(src):
        if src[j]=='{': depth += 1
        elif src[j]=='}':
            depth -= 1
            if depth==0:
                return src[:i] + new + src[j+1:]
        j += 1
    raise SystemExit(f'v795 function end not found: {sig}')

new_monitor = r'''    fn live_root_monitor(&mut self, reader: &Gen2Reader) {
        if !self.practical_scan_enabled || !self.practical_live_scan
            || self.probe_session || self.practical_active || self.practical_candidate_valid
        { return; }

        let cur = rng_advance();
        let da = cur.wrapping_sub(self.practical_live_last_advance);
        if da == 0 { return; }
        self.practical_live_last_advance = cur;
        self.practical_live_checked = self.practical_live_checked.saturating_add(1);

        let r = latest_pre_vblank_ring();
        let n = (r.count as usize).min(PRE_VBLANK_RING_LEN);
        if n != PRE_VBLANK_RING_LEN { return; }
        let (last, _) = pre_ring_sample(&r, n - 1);
        let lag = cur.wrapping_sub(last);
        let (proto0, mut rot, best, second, ok) = classify_pre_ring(&r);
        self.phase_best_score = best;
        self.phase_second_score = second;
        self.phase_consecutive = ok;
        self.phase_now_proto = proto0;
        self.phase_now_rot = rot;
        self.phase_now_lag = lag.min(255) as u8;
        if lag == 1 { rot = rot.wrapping_add(1) & 15; }
        if lag != 0 || !ok || best != 0 { return; }
        self.phase_exact_count = self.phase_exact_count.saturating_add(1);
        self.phase_now_rot = rot;

        if !practical::multipre_supported(proto0, rot) { return; }

        let mut bucket_opt: Option<u8> = None;
        if proto0 == b'A' && rot == 10 {
            let (_, p0) = pre_ring_sample(&r, 0);
            let pd = p0.wrapping_sub(0x0035) & 0x3fff;
            if (pd & 0x003f) == 0 {
                let b = ((pd >> 6) & 0xff) as u8;
                self.bucket_current = b;
                bucket_opt = Some(b);
            }
        }

        let Some(ai0) = add_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let Some(si0) = sub_div_tracker().index() else {
            self.practical_live_index_wait = self.practical_live_index_wait.saturating_add(1);
            return;
        };
        let ai = (ai0 as u32) & 0x3fff;
        let si = (si0 as u32) & 0x3fff;

        self.practical_empirical_eval = self.practical_empirical_eval.saturating_add(1);
        let Some(mp) = practical::evaluate_multi_pre_inverse(
            proto0, rot, bucket_opt, reader.rng_state(), measured_div(), ai, si
        ) else {
            return;
        };

        self.phase_target_proto = proto0;
        self.phase_target_rot = rot;
        self.multipre_score = mp.score;
        self.multipre_branches = mp.branches;
        self.bucket_model_active = mp.bucket_model;
        self.bucket_current = mp.bucket;
        self.bucket_anchor = mp.anchor;
        self.bucket_distance = mp.distance;
        self.bucket_radius = if mp.bucket_model { 16 } else { 0 };
        self.bucket_expected_post_proto = mp.post_proto;
        self.bucket_expected_post_rot = mp.post_rot;

        self.practical_live_found_advance = cur;
        self.practical_live_found_state = reader.rng_state();
        self.practical_live_found_div = measured_div();
        self.practical_live_found_tick = pnp::system_tick();
        self.practical_live_found_ai = ai;
        self.practical_live_found_si = si;

        self.bind_practical_prediction(mp.prediction);
        self.practical_live_found_lane = 253;
        self.practical_empirical = mp.empirical;
        self.practical_empirical_candidates = self.practical_empirical_candidates.saturating_add(1);
        self.practical_live_scan = false;
        pre_vblank_timing_capture_stop();
        pnp::request_pause();
    }'''
t = replace_fn(t, '    fn live_root_monitor(&mut self, reader: &Gen2Reader)', new_monitor)

donor_defs = r'''
#[derive(Clone, Copy)]
struct V795Donor {
    run: u8, j: i16, post_proto: u8, post_rot: u8,
    addr: [u16; 3], last: [u16; 3],
    f1: [u8; 3], f2: [u8; 3], f3: [u8; 3],
    nd: [u8; 3], md: [u8; 3], nl: [u8; 3],
    lc: [u8; 3], vc: [u8; 3], vr: [u8; 3],
}

const V795_DONORS: [V795Donor; 11] = [
    V795Donor{run:4,j:-330,post_proto:b'B',post_rot:9,addr:[0x73ab,0x74c6,0x7587],last:[0x737b,0x0000,0x755f],f1:[3,1,3],f2:[1,1,1],f3:[0,0,0],nd:[0x08,0x24,0x12],md:[0xf4,0xa8,0x30],nl:[0x06,0x06,0x0c],lc:[0,0,0],vc:[0x10,0x00,0x00],vr:[0x55,0x54,0x53]},
    V795Donor{run:5,j:37,post_proto:b'C',post_rot:1,addr:[0x72eb,0x73fc,0x74ef],last:[0x737b,0x0000,0x755f],f1:[1,1,1],f2:[1,1,1],f3:[1,1,1],nd:[0x23,0x23,0x23],md:[0x00,0x00,0x00],nl:[0x0c,0x06,0x0c],lc:[0,0,0],vc:[0x00,0x0a,0x00],vr:[0x51,0x52,0x55]},
    V795Donor{run:6,j:1376,post_proto:b'B',post_rot:8,addr:[0x72eb,0x73fc,0x74ef],last:[0x737b,0x0000,0x755f],f1:[1,1,1],f2:[1,1,1],f3:[0,1,1],nd:[0x20,0x20,0x20],md:[0x00,0x00,0x00],nl:[0x0c,0x06,0x0c],lc:[0,0,0],vc:[0x00,0x07,0x00],vr:[0x54,0x52,0x52]},
    V795Donor{run:7,j:-27,post_proto:b'C',post_rot:14,addr:[0x7339,0x7473,0x7576],last:[0x732e,0x0000,0x7550],f1:[1,1,3],f2:[1,1,1],f3:[1,0,0],nd:[0x04,0x04,0x04],md:[0xa0,0xa0,0xa0],nl:[0x06,0x06,0x0c],lc:[0,0,0],vc:[0x0c,0x03,0x0c],vr:[0x53,0x50,0x54]},
    V795Donor{run:8,j:1053,post_proto:b'A',post_rot:1,addr:[0x72f8,0x741f,0x7509],last:[0x0000,0x0000,0x0000],f1:[1,1,1],f2:[1,1,1],f3:[0,0,0],nd:[0x43,0x0b,0x0b],md:[0x18,0xb0,0xb0],nl:[0x0c,0x06,0x0c],lc:[0,0,0],vc:[0x00,0x00,0x0a],vr:[0x52,0x51,0x54]},
    V795Donor{run:9,j:1186,post_proto:b'C',post_rot:1,addr:[0x7318,0x7446,0x7535],last:[0x0000,0x0000,0x0000],f1:[1,1,1],f2:[1,1,1],f3:[1,0,0],nd:[0x0a,0x0a,0x0a],md:[0x90,0x90,0x90],nl:[0x06,0x06,0x0c],lc:[0,0,0],vc:[0x09,0x09,0x09],vr:[0x51,0x54,0x54]},
    V795Donor{run:10,j:199,post_proto:b'C',post_rot:3,addr:[0x73aa,0x74c6,0x7587],last:[0x737b,0x0000,0x755f],f1:[3,1,3],f2:[1,1,1],f3:[0,1,0],nd:[0x02,0x27,0x15],md:[0xb8,0xa8,0x30],nl:[0x06,0x06,0x0c],lc:[0,0,0],vc:[0x0a,0x01,0x01],vr:[0x55,0x50,0x55]},
    V795Donor{run:11,j:32,post_proto:b'B',post_rot:8,addr:[0x72f7,0x741d,0x7506],last:[0x0000,0x0000,0x0000],f1:[1,1,1],f2:[1,1,1],f3:[0,1,1],nd:[0x4c,0x02,0x4c],md:[0xc0,0xe0,0xc0],nl:[0x0c,0x06,0x0c],lc:[0,0,0],vc:[0x00,0x0a,0x01],vr:[0x52,0x50,0x51]},
    V795Donor{run:12,j:29,post_proto:b'A',post_rot:1,addr:[0x731a,0x7447,0x7536],last:[0x0000,0x0000,0x0000],f1:[1,1,1],f2:[1,1,1],f3:[1,0,0],nd:[0x07,0x07,0x07],md:[0x08,0x08,0x08],nl:[0x06,0x06,0x0c],lc:[0,0,0],vc:[0x05,0x05,0x05],vr:[0x51,0x54,0x54]},
    V795Donor{run:13,j:861,post_proto:b'A',post_rot:1,addr:[0x72f8,0x741f,0x7508],last:[0x0000,0x0000,0x0000],f1:[1,1,1],f2:[1,1,1],f3:[1,1,0],nd:[0x59,0x21,0x0f],md:[0x18,0xb0,0x38],nl:[0x0c,0x06,0x0c],lc:[0,0,0],vc:[0x0d,0x0d,0x0d],vr:[0x55,0x54,0x55]},
    V795Donor{run:14,j:-544,post_proto:b'D',post_rot:1,addr:[0x7341,0x7478,0x757a],last:[0x732e,0x0000,0x7550],f1:[1,1,3],f2:[1,1,1],f3:[1,1,0],nd:[0x09,0x1b,0x09],md:[0x08,0x80,0x08],nl:[0x06,0x06,0x0c],lc:[0,0,0],vc:[0x10,0x07,0x07],vr:[0x53,0x55,0x54]},
];

static mut V795_DONOR_RUN: u8 = 0;
static mut V795_DONOR_J: i16 = 0;
static mut V795_DONOR_POST_PROTO: u8 = 0;
static mut V795_DONOR_POST_ROT: u8 = 0;
static mut V795_DONOR_EXPECTED_PROTO: u8 = 0;
static mut V795_DONOR_EXPECTED_ROT: u8 = 0;
static mut V795_DONOR_ACCEPTED: bool = false;

fn v795_pre8(ch: usize, off: usize) -> u8 {
    unsafe { V792_AUDIO_PRE[1 + ch * 0x32 + off] }
}
fn v795_pre16(ch: usize, off: usize) -> u16 {
    (v795_pre8(ch, off) as u16) | ((v795_pre8(ch, off + 1) as u16) << 8)
}
fn v795_matches(d: &V795Donor) -> bool {
    for ch in 0..3usize {
        if v795_pre16(ch,0x06) != d.addr[ch] { return false; }
        if v795_pre16(ch,0x08) != d.last[ch] { return false; }
        if (v795_pre8(ch,0x03)&7) != d.f1[ch] { return false; }
        if (v795_pre8(ch,0x04)&7) != d.f2[ch] { return false; }
        if (v795_pre8(ch,0x05)&3) != d.f3[ch] { return false; }
        if v795_pre8(ch,0x15) != d.nd[ch] { return false; }
        if v795_pre8(ch,0x16) != d.md[ch] { return false; }
        if v795_pre8(ch,0x2d) != d.nl[ch] { return false; }
        if v795_pre8(ch,0x18) != d.lc[ch] { return false; }
        if v795_pre8(ch,0x1d) != d.vc[ch] { return false; }
        if v795_pre8(ch,0x20) != d.vr[ch] { return false; }
    }
    true
}
'''
t = t.replace('impl Trace {', donor_defs + '\nimpl Trace {', 1)

method = r'''    pub fn audio_donor_gate_at_pause(&mut self, reader: &Gen2Reader) -> u32 {
        unsafe {
            V795_DONOR_RUN = 0;
            V795_DONOR_J = 0;
            V795_DONOR_POST_PROTO = 0;
            V795_DONOR_POST_ROT = 0;
            V795_DONOR_EXPECTED_PROTO = self.bucket_expected_post_proto;
            V795_DONOR_EXPECTED_ROT = self.bucket_expected_post_rot;
            V795_DONOR_ACCEPTED = false;
        }

        let snapshot_ok = unsafe {
            V792_AUDIO_PRE_VALID && V792_AUDIO_PRE_TARGET == rng_advance()
        };
        let mut hit: Option<V795Donor> = None;
        if snapshot_ok {
            for d in V795_DONORS.iter() {
                if v795_matches(d) { hit = Some(*d); break; }
            }
        }

        if let Some(d) = hit {
            let expected_ok = self.bucket_expected_post_proto != 0
                && self.bucket_expected_post_proto == d.post_proto
                && self.bucket_expected_post_rot == d.post_rot;
            unsafe {
                V795_DONOR_RUN = d.run;
                V795_DONOR_J = d.j;
                V795_DONOR_POST_PROTO = d.post_proto;
                V795_DONOR_POST_ROT = d.post_rot;
                V795_DONOR_ACCEPTED = expected_ok;
            }
            if expected_ok {
                return 0x80000000u32 | d.run as u32
                    | ((d.post_proto as u32) << 8) | ((d.post_rot as u32) << 16);
            }
        }

        self.stop();
        self.probe_session = false;
        self.probe_active = false;
        self.probe_result = None;
        self.start_practical_scan(reader);
        0
    }

'''
t = t.replace('impl Trace {\n', 'impl Trace {\n' + method, 1)

save_anchor = '''        pnp::trace_file_close();
        self.save_index += 1;'''
save_block = r'''        line.clear();
        unsafe {
            let _ = write!(line,
                "\ndonor_gate,version,run,j,post_proto,post_rot,expected_proto,expected_rot,accepted\nDONORGATE,V795,{},{},{},{},{},{},{}\n",
                V795_DONOR_RUN, V795_DONOR_J,
                if V795_DONOR_POST_PROTO==0 {'?'} else {V795_DONOR_POST_PROTO as char},
                V795_DONOR_POST_ROT,
                if V795_DONOR_EXPECTED_PROTO==0 {'?'} else {V795_DONOR_EXPECTED_PROTO as char},
                V795_DONOR_EXPECTED_ROT, V795_DONOR_ACCEPTED as u8);
        }
        pnp::trace_file_write(line.as_bytes());

        pnp::trace_file_close();
        self.save_index += 1;'''
t = rep(t, save_anchor, save_block, 'donor telemetry before close')

f += r'''

pub fn suicune_audio_donor_gate() -> u32 {
    let reader = Gen2Reader::crystal();
    let state = unsafe { get_state() };
    state.trace.audio_donor_gate_at_pause(&reader)
}
'''
modp=Path('reader_core/src/crystal/mod.rs')
modtxt=modp.read_text()
if 'pub use frame::suicune_audio_donor_gate;' not in modtxt:
    modtxt += '\npub use frame::suicune_audio_donor_gate;\n'
    modp.write_text(modtxt)

l += r'''

#[no_mangle]
pub extern "C" fn suicune_audio_donor_gate() -> u32 {
    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {
        crystal::suicune_audio_donor_gate()
    } else { 0 }
}
'''
if 'u32 suicune_audio_donor_gate();' not in h:
    h += '\nu32 suicune_audio_donor_gate();\n'

old = '''                suicune_neutral_probe_pending = false;
                arm_suicune_probe();
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;
                suicune_observe_reset();'''
new = '''                suicune_neutral_probe_pending = false;
                arm_suicune_probe();
                u32 donor_gate = suicune_audio_donor_gate();
                if ((donor_gate & 0x80000000U) == 0)
                {
                    suicune_live_pass_ready = false;
                    suicune_wait_up_after_b = false;
                    suicune_neutral_probe_remaining = 0;
                    suicune_neutral_probe_executed = 0;
                    fixed_frames_remaining = 0;
                    fixed_run_pending = false;
                    fixed_armed = false;
                    suicune_auto_resume_pending = false;
                    suicune_phase_lock_active = false;
                    suicune_start_phase_lock_active = false;
                    suicune_root_lock_active = false;
                    suicune_root_lock_ready = false;
                    suicune_root_lock_failed = false;
                    suicune_root_lock_steps = 0;
                    suicune_root_lock_last_cell = 0;
                    is_paused = false;
                    break;
                }
                suicune_live_pass_ready = arm_suicune_live_pass() != 0;
                suicune_observe_reset();'''
c = rep(c, old, new, 'insert pause-time donor gate')

oldsel = '''        // v7.8.6 neutral-frame selector. Default 3F. X/Y change only the
        // number of natural, input-neutral VC frames inserted before the probe
        // is armed; host wall-clock phase is not a control variable.
        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)
        {
            if (just_pressed & KEY_X)
            {
                suicune_neutral_probe_frames++;
                if (suicune_neutral_probe_frames > 3U) suicune_neutral_probe_frames = 1U;
                suicune_start_phase_slot = suicune_neutral_probe_frames; // telemetry only
                continue;
            }
            if (just_pressed & KEY_Y)
            {
                if (suicune_neutral_probe_frames <= 1U) suicune_neutral_probe_frames = 3U;
                else suicune_neutral_probe_frames--;
                suicune_start_phase_slot = suicune_neutral_probe_frames; // telemetry only
                continue;
            }
        }
'''
newsel = '''        // v7.9.5 production donor gate uses fixed measured neutral 3F.
        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)
        {
            suicune_neutral_probe_frames = 3U;
            suicune_start_phase_slot = 3U;
        }
'''
c = rep(c, oldsel, newsel, 'fix neutral transport to 3F')

T.write_text(t); F.write_text(f); L.write_text(l); H.write_text(h); C.write_text(c)
print('Applied v7.9.5: shiny rolling restored + exact AUDIOPRE donor/POST gate + auto reject/rescan')
