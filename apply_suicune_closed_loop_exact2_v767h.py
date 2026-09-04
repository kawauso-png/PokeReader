from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767h {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)


def remove_braced_if(src, marker, label):
    a = src.find(marker)
    if a < 0:
        raise SystemExit(f'v767h {label}: marker not found')
    b = src.find('{', a)
    if b < 0:
        raise SystemExit(f'v767h {label}: opening brace missing')
    depth = 0
    end = -1
    for i in range(b, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise SystemExit(f'v767h {label}: closing brace missing')
    while end < len(src) and src[end] in ' \t':
        end += 1
    if end < len(src) and src[end] == '\n':
        end += 1
    return src[:a] + src[end:]

# v7.6.7h stays inside the agreed boundary: observation + Pause/Resume +
# physical UP only. No HID masking, no FF00 substitution, no GB/RNG/DIV/DV/save
# writes. FFA8 hJoyDown is the authoritative accepted-input observation.

H = Path('reader_core/src/crystal/hook.rs')
h = H.read_text()

h = rep(h, 'const LIVE_SAMPLE_CAP: usize = 22;', 'const LIVE_SAMPLE_CAP: usize = 96;', 'sample cap')

h = rep(h,
'''    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
}''',
'''    pub joy_up_counts: [u8; 8],
    pub joy_first_up_rel: [u8; 8],
    pub exact2_up_advances: u8,
    pub exact2_last_up_advance: u32,
    pub exact2_first_up_advance: u32,
    pub exact2_second_up_advance: u32,
    pub exact2_pause_requested: u8,
    pub exact2_release_confirmed: u8,
    pub exact2_first_clear_advance: u32,
}''',
'exact2 telemetry fields')

h = rep(h,
'''        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
    };''',
'''        joy_up_counts: [0; 8],
        joy_first_up_rel: [0xff; 8],
        exact2_up_advances: 0,
        exact2_last_up_advance: 0,
        exact2_first_up_advance: 0,
        exact2_second_up_advance: 0,
        exact2_pause_requested: 0,
        exact2_release_confirmed: 0,
        exact2_first_clear_advance: 0,
    };''',
'exact2 telemetry defaults')

h = rep(h,
'''static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;''',
'''static mut LIVE_PASS_ARMED: bool = false;
static mut LIVE_PASS: LivePassTelemetry = LivePassTelemetry::EMPTY;
static mut EXACT2_RELEASE_WAITING: bool = false;''',
'exact2 state')

h = rep(h,
'''        LIVE_PASS_ARMED = capable;
    }
    capable
}''',
'''        LIVE_PASS_ARMED = capable;
        EXACT2_RELEASE_WAITING = false;
    }
    capable
}''',
'arm reset')

anchor = 'pub fn live_pass_telemetry() -> LivePassTelemetry {'
insert = '''pub fn exact2_release_waiting() -> bool {
    unsafe { EXACT2_RELEASE_WAITING }
}

pub fn exact2_release_confirmed() {
    unsafe {
        EXACT2_RELEASE_WAITING = false;
        LIVE_PASS.exact2_release_confirmed = 1;
    }
}

'''
if h.count(anchor) != 1:
    raise SystemExit(f'v767h handshake anchor count {h.count(anchor)}')
h = h.replace(anchor, insert + anchor, 1)

h = rep(h,
'''        let hjoy = joy[JOY_HJOY_DOWN];
        let up = (hjoy & PAD_UP) != 0;

        if before_pass {''',
'''        let hjoy = joy[JOY_HJOY_DOWN];
        let up = (hjoy & PAD_UP) != 0;

        // Count distinct RNG advances where Crystal itself reports UP held.
        if up {
            if LIVE_PASS.exact2_up_advances == 0 || LIVE_PASS.exact2_last_up_advance != now {
                LIVE_PASS.exact2_last_up_advance = now;
                LIVE_PASS.exact2_up_advances = LIVE_PASS.exact2_up_advances.saturating_add(1);
                if LIVE_PASS.exact2_up_advances == 1 {
                    LIVE_PASS.exact2_first_up_advance = now;
                } else if LIVE_PASS.exact2_up_advances == 2 {
                    LIVE_PASS.exact2_second_up_advance = now;
                    LIVE_PASS.exact2_pause_requested = 1;
                    EXACT2_RELEASE_WAITING = true;
                    pnp::request_pause();
                }
            }
        } else if LIVE_PASS.exact2_release_confirmed != 0 && LIVE_PASS.exact2_first_clear_advance == 0 {
            LIVE_PASS.exact2_first_clear_advance = now;
        }

        if before_pass {''',
'exact2 observer')
H.write_text(h)

M = Path('reader_core/src/crystal/mod.rs')
m = M.read_text()
m = rep(m,
'pub use hook::{arm_live_pass_probe, init_crystal};',
'pub use hook::{arm_live_pass_probe, exact2_release_confirmed, exact2_release_waiting, init_crystal};',
'crystal exports')
M.write_text(m)

L = Path('reader_core/src/lib.rs')
l = L.read_text()
anchor = '''#[no_mangle]
pub extern "C" fn arm_suicune_live_pass() -> u32 {'''
insert = '''#[no_mangle]
pub extern "C" fn suicune_exact2_release_waiting() -> u32 {
    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {
        return crystal::exact2_release_waiting() as u32;
    }
    0
}

#[no_mangle]
pub extern "C" fn suicune_exact2_release_confirmed() {
    if let Ok(LoadedTitle::CrystalJp) = loaded_title() {
        crystal::exact2_release_confirmed();
    }
}

'''
if l.count(anchor) != 1:
    raise SystemExit(f'v767h lib anchor count {l.count(anchor)}')
l = l.replace(anchor, insert + anchor, 1)
L.write_text(l)

P = Path('3gx/includes/pokereader.h')
p = P.read_text()
needle = 'u32 arm_suicune_live_pass();\n'
if p.count(needle) != 1:
    raise SystemExit(f'v767h header arm count {p.count(needle)}')
p = p.replace(needle, needle + 'u32 suicune_exact2_release_waiting();\nvoid suicune_exact2_release_confirmed();\n', 1)
P.write_text(p)

C = Path('3gx/sources/main.c')
c = C.read_text()
c = rep(c,
'''        u32 just_pressed = host_just_pressed();
        u32 held = get_current_keys();
''',
'''        u32 just_pressed = host_just_pressed();
        u32 held = get_current_keys();

        // After Crystal accepted UP on two advances, remain frozen until the
        // user physically releases UP; then resume the untouched game.
        if (suicune_exact2_release_waiting())
        {
            if ((held & KEY_DUP) == 0)
            {
                suicune_exact2_release_confirmed();
                fixed_frames_remaining = 0;
                fixed_run_pending = false;
                is_paused = false;
                break;
            }
            svcSleepThread(1000000);
            continue;
        }
''',
'pause release checkpoint')
C.write_text(c)

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

# Remove the old +22 live-pass diagnostic stop.
t = remove_braced_if(t, '        if self.probe_session && live_pass_should_finish()', '22-frame auto-stop')
t = t.replace('live_pass_should_finish, ', '')
t = t.replace(', live_pass_should_finish', '')

# Restore rel40 evaluation but make it diagnostic/non-terminal. Even when the
# inverse model has no shiny prediction, continue the native encounter so final
# raw DV remains ground truth in the same CSV.
v766_rel40_stop = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                // v7.6.6 ends every diagnostic run at rel40 after recording the
                // actual POST/J/state/div and suffix-gate support.  This avoids a
                // 700-frame tail and makes each M replicate fast and comparable.
                self.practical_fail(13);return
'''
rel40_nonterminal = '''                let g=practical::evaluate_actual_post_inverse_v763(post.proto,post.rot40,e.state,e.div,ai,si);
                self.v763_gate_models=g.models;self.v763_gate_evaluated=g.evaluated;self.v763_gate_shiny_models=g.shiny_models;
                if let Some(x)=g.prediction{
                    self.practical_empirical=x.lane_id>=101&&x.lane_id<200;
                    self.bucket_model_active=x.lane_id>=200;
                    self.rebind_practical_post_v690(x,post.proto,post.rot40);
                }
                // Do not make prediction support a condition for collecting the
                // actual tail. Generic probe/result detection remains active.
                self.practical_active=false;
                return
'''
t = rep(t, v766_rel40_stop, rel40_nonterminal, 'rel40 nonterminal continuation')

t = rep(t,
'                if !post.valid||post.best_score!=0{self.practical_fail(12);return}',
'                if !post.valid||post.best_score!=0{self.practical_miss=12;self.practical_active=false;return}',
'nonterminal POST classification miss')

t = rep(t, 'LIVEPASS,V767F,', 'LIVEPASS,V767H,', 'main lineage')
t = rep(t, 'LIVEPASSHOST,V767F,', 'LIVEPASSHOST,V767H,', 'host lineage')
t = rep(t, 'JOYMAP,V767F,', 'JOYMAP,V767H,', 'joymap lineage')
t = rep(t, 'JOYFRAME,V767F,', 'JOYFRAME,V767H,', 'joyframe lineage')
t = t.replace('for i in 0..n.min(22) {', 'for i in 0..n.min(96) {', 1)

anchor = '        // Full per-advance raw chain. This is diagnostic-only and is exported'
insert = '''        line.clear();
        let _ = write!(
            line,
            "\\nexact2,version,accepted_up_advances,first_up_advance,second_up_advance,pause_requested,release_confirmed,first_clear_after_release\\nEXACT2,V767H,{},{},{},{},{},{}\\n",
            lp.exact2_up_advances,
            lp.exact2_first_up_advance,
            lp.exact2_second_up_advance,
            lp.exact2_pause_requested,
            lp.exact2_release_confirmed,
            lp.exact2_first_clear_advance
        );
        pnp::trace_file_write(line.as_bytes());

'''
if t.count(anchor) != 1:
    raise SystemExit(f'v767h exact2 CSV anchor count {t.count(anchor)}')
t = t.replace(anchor, insert + anchor, 1)
T.write_text(t)

print('Applied v7.6.7h: closed-loop physical-UP Exact2 + rel40 diagnostics + native final DV')
