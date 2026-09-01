from pathlib import Path
import re

ROOT = Path('.')
TRACE = ROOT / 'reader_core/src/crystal/trace.rs'
PRACTICAL = ROOT / 'reader_core/src/crystal/practical.rs'
HOOK = ROOT / 'reader_core/src/pnp/hook.rs'
BIND = ROOT / 'reader_core/src/pnp/bindings.rs'
MAIN = ROOT / '3gx/sources/main.c'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {n}')
    return text.replace(old, new, 1)


def sub_once(text: str, pattern: str, repl, label: str, flags=0) -> str:
    out, n = re.subn(pattern, repl, text, count=1, flags=flags)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly one regex match, found {n}')
    return out

# practical.rs: attach authoritative post-stop1 branch IDs to the six known
# donor lanes, and allow an existing suffix donor to be evaluated from the
# actual rel40 state/DIV instead of from the PRE root.
p = PRACTICAL.read_text()
p = replace_once(
    p,
    '    proto: u8,\n    rot: u8,\n',
    '    proto: u8,\n    rot: u8,\n    post_proto: u8,\n    post_rot: u8,\n',
    'Lane post fields',
)

post_map = {
    1: ('A', 2),   # source 0087
    2: ('B', 8),   # source 0094
    3: ('B', 9),   # source 0095
    4: ('A', 2),   # source 0089
    5: ('D', 2),   # source 0096
    6: ('B', 14),  # source 0086
}
for lane_id, (proto, rot) in post_map.items():
    pattern = rf'(const L{lane_id}: Lane = Lane \{{.*?\n    proto: b\'[A-D]\',\n    rot: \d+,\n)'
    p = sub_once(
        p,
        pattern,
        lambda m, proto=proto, rot=rot: m.group(1) + f"    post_proto: b'{proto}',\n    post_rot: {rot},\n",
        f'L{lane_id} post identity',
        flags=re.S,
    )

marker = 'pub const SEARCH_HORIZON: u32 = 12000;\n'
insert = r'''pub fn lane_for_post(proto: u8, rot: u8) -> Option<u8> {
    // Multiple PRE lanes may collapse onto the same clean POST branch
    // (currently L1/L4 -> A/r2). The suffix is equivalent modulo the 8-bit
    // arithmetic used by apply_sums(), so the first matching donor is enough.
    for id in 1..=LANE_COUNT {
        let l = lane(id);
        if l.post_proto == proto && l.post_rot == rot {
            return Some(id);
        }
    }
    None
}

pub fn evaluate_post(id: u8, state40: u16, div40: u16) -> Option<Prediction> {
    // Re-root the donor at actual rel40. The cumulative tables are all from
    // Target, but apply_sums composes: subtracting the rel40 cumulative sums
    // yields exactly the suffix transformation from rel40 onward.
    let l = lane(id);
    let av40 = (div40 >> 8) as u8;
    let sv40 = div40 as u8;
    let av0 = av40.wrapping_sub(l.off40_a);
    let sv0 = sv40.wrapping_sub(l.off40_s);

    let suffix_full_a = l.full_a[av0 as usize].wrapping_sub(l.p40_a[av0 as usize]);
    let suffix_full_s = l.full_s[sv0 as usize].wrapping_sub(l.p40_s[sv0 as usize]);
    let predeep = apply_sums(state40, suffix_full_a, suffix_full_s);
    let last_a = av0.wrapping_add(l.last_a);
    let last_s = sv0.wrapping_add(l.last_s);

    let mut support = 0u8;
    let mut mask = 0u8;
    let mut first_raw = 0u16;
    for i in 0..5usize {
        let mut st = predeep;
        let mut lows = [0u8; 3];
        for j in 0..3usize {
            st = upd(
                st,
                last_a.wrapping_add(DEEP_A[i][j]),
                last_s.wrapping_add(DEEP_S[i][j]),
            );
            lows[j] = st as u8;
        }
        if lows[0] >= 0xc0 {
            continue;
        }
        let raw = ((lows[1] as u16) << 8) | lows[2] as u16;
        if shiny(raw) {
            support = support.saturating_add(DEEP_WEIGHT[i]);
            mask |= 1u8 << i;
            if first_raw == 0 {
                first_raw = raw;
            }
        }
    }
    if support < MIN_SUPPORT_WEIGHT {
        return None;
    }

    let suffix716_a = l.p716_a[av0 as usize].wrapping_sub(l.p40_a[av0 as usize]);
    let suffix716_s = l.p716_s[sv0 as usize].wrapping_sub(l.p40_s[sv0 as usize]);
    let e716_state = apply_sums(state40, suffix716_a, suffix716_s);
    let e716_div = ((av40.wrapping_add(l.off716_a.wrapping_sub(l.off40_a)) as u16) << 8)
        | sv40.wrapping_add(l.off716_s.wrapping_sub(l.off40_s)) as u16;
    let e717_div = ((av40.wrapping_add(l.off717_a.wrapping_sub(l.off40_a)) as u16) << 8)
        | sv40.wrapping_add(l.off717_s.wrapping_sub(l.off40_s)) as u16;
    let e717_state = upd(e716_state, (e717_div >> 8) as u8, e717_div as u8);

    Some(Prediction {
        lane_id: id,
        source: l.source,
        support_weight: support,
        shiny_mask: mask,
        raw: first_raw,
        expected40_state: state40,
        expected40_div: div40,
        expected716_state: e716_state,
        expected716_div: e716_div,
        expected717_state: e717_state,
        expected717_div: e717_div,
    })
}

'''
p = replace_once(p, marker, insert + marker, 'post evaluator insertion')
PRACTICAL.write_text(p)

# pnp bridge + C host: a retry is different from a normal resume. ERR2/ERR3
# leave the game running for 512 presented frames, then C automatically pauses
# and invokes the existing frozen search entry point. Total retry-running time
# is capped at 3600 frames (~60 s) before leaving the last E2/E3 visible.
h = HOOK.read_text()
h = replace_once(
    h,
    'pub fn request_resume() {\n    unsafe { bindings::host_request_resume() }\n}\n',
    '''pub fn request_resume() {\n    unsafe { bindings::host_request_resume() }\n}\n\n/// Resume specifically for an ERR2/ERR3 rolling-search retry.\npub fn request_roll_retry() {\n    unsafe { bindings::host_request_roll_retry() }\n}\n\npub fn suicune_roll_active() -> bool {\n    unsafe { bindings::host_suicune_roll_active() != 0 }\n}\n\npub fn suicune_roll_total() -> u32 {\n    unsafe { bindings::host_suicune_roll_total() }\n}\n''',
    'pnp rolling wrappers',
)
HOOK.write_text(h)

b = BIND.read_text()
b = replace_once(
    b,
    '    pub fn host_request_pause();\n    pub fn host_request_resume();\n',
    '    pub fn host_request_pause();\n    pub fn host_request_resume();\n    pub fn host_request_roll_retry();\n    pub fn host_suicune_roll_active() -> u32;\n    pub fn host_suicune_roll_total() -> u32;\n',
    'binding declarations',
)
b = replace_once(
    b,
    '    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_request_resume() {}\n',
    '    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_request_resume() {}\n    #[no_mangle]\n    pub extern "C" fn host_request_roll_retry() {}\n    #[no_mangle]\n    pub extern "C" fn host_suicune_roll_active() -> u32 { 0 }\n    #[no_mangle]\n    pub extern "C" fn host_suicune_roll_total() -> u32 { 0 }\n',
    'binding test stubs',
)
BIND.write_text(b)

m = MAIN.read_text()
m = replace_once(
    m,
    '// Rust uses this only for reset-friendly search failures (ERR2 / ERR3).\n// It does not inject any game input; it merely leaves PokeReader\'s own pause\n// loop so the VC software reset can be used normally.\n',
    '// Normal search success resumes WAIT immediately; ERR2/ERR3 use the\n// separate bounded rolling-retry host path below. Neither path injects input.\n',
    'C resume comment',
)
m = replace_once(
    m,
    'static u32 trace_save_req = 0;\n',
    '''static u32 trace_save_req = 0;\n\n// v6.5.9 automatic rolling search. Heavy 12k projection still runs only\n// inside the frozen pause loop; live frames merely count down to the next\n// retry boundary.\n#define SUICUNE_ROLL_RETRY_FRAMES 512U\n#define SUICUNE_ROLL_MAX_FRAMES 3600U\nstatic bool suicune_roll_retry_active = false;\nstatic bool suicune_roll_autosearch_pending = false;\nstatic u32 suicune_roll_retry_countdown = 0;\nstatic u32 suicune_roll_total_frames = 0;\n''',
    'C rolling state',
)
old_resume = '''void host_request_resume(void)\n{\n    is_paused = false;\n    fixed_frames_remaining = 0;\n    fixed_run_pending = false;\n}\n'''
new_resume = '''void host_request_resume(void)\n{\n    is_paused = false;\n    fixed_frames_remaining = 0;\n    fixed_run_pending = false;\n    // Normal resume means a usable candidate queue was found. Stop any\n    // outstanding E2/E3 retry timer.\n    suicune_roll_retry_active = false;\n    suicune_roll_autosearch_pending = false;\n    suicune_roll_retry_countdown = 0;\n}\n\nvoid host_request_roll_retry(void)\n{\n    is_paused = false;\n    fixed_frames_remaining = 0;\n    fixed_run_pending = false;\n    suicune_roll_autosearch_pending = false;\n    suicune_roll_retry_active = true;\n    suicune_roll_retry_countdown = SUICUNE_ROLL_RETRY_FRAMES;\n}\n\nu32 host_suicune_roll_active(void)\n{\n    return (suicune_roll_retry_active || suicune_roll_autosearch_pending) ? 1U : 0U;\n}\n\nu32 host_suicune_roll_total(void)\n{\n    return suicune_roll_total_frames;\n}\n'''
m = replace_once(m, old_resume, new_resume, 'C host resume/retry')

old_pause_entry = '''    if (host_is_just_pressed(KEY_START | KEY_SELECT) || (is_gen_2 && host_is_just_pressed(KEY_L | KEY_R)))\n    {\n        is_paused = true;\n    }\n\n    while (is_paused && !isTopScreen)\n    {\n        scan_input();\n'''
new_pause_entry = '''    if (host_is_just_pressed(KEY_START | KEY_SELECT) || (is_gen_2 && host_is_just_pressed(KEY_L | KEY_R)))\n    {\n        // A deliberate manual pause is also an explicit rolling-search abort.\n        suicune_roll_retry_active = false;\n        suicune_roll_autosearch_pending = false;\n        suicune_roll_retry_countdown = 0;\n        is_paused = true;\n    }\n\n    while (is_paused && !isTopScreen)\n    {\n        // Auto-retry calls the exact same Rust search function as Y+DOWN, but\n        // only after the game is frozen. Success or E2/E3 will resume through\n        // their respective host callbacks; hard errors stay paused.\n        if (suicune_roll_autosearch_pending)\n        {\n            suicune_roll_autosearch_pending = false;\n            search_suicune_practical_targets();\n            if (!is_paused) break;\n            svcSleepThread(1000000);\n            continue;\n        }\n\n        scan_input();\n'''
m = replace_once(m, old_pause_entry, new_pause_entry, 'C auto-search pause loop')

old_hotkey = '''            if (just_pressed & KEY_DDOWN)\n            {\n                search_suicune_practical_targets();\n                svcSleepThread(1000000);\n                continue;\n            }\n'''
new_hotkey = '''            if (just_pressed & KEY_DDOWN)\n            {\n                // One manual Y+DOWN starts a fresh bounded rolling session.\n                suicune_roll_retry_active = false;\n                suicune_roll_autosearch_pending = false;\n                suicune_roll_retry_countdown = 0;\n                suicune_roll_total_frames = 0;\n                search_suicune_practical_targets();\n                svcSleepThread(1000000);\n                continue;\n            }\n'''
m = replace_once(m, old_hotkey, new_hotkey, 'C Y+DOWN rolling start')

old_top = '''    if (isTopScreen)\n    {\n        scan_input();\n        run_frame();\n        draw_to_screen(screenId, fb_a, stride, format);\n    }\n'''
new_top = '''    if (isTopScreen)\n    {\n        scan_input();\n\n        if (suicune_roll_retry_active && !is_paused)\n        {\n            if (suicune_roll_total_frames < SUICUNE_ROLL_MAX_FRAMES)\n                suicune_roll_total_frames++;\n            if (suicune_roll_retry_countdown > 0)\n                suicune_roll_retry_countdown--;\n\n            if (suicune_roll_total_frames >= SUICUNE_ROLL_MAX_FRAMES)\n            {\n                // Leave the last Rust E2/E3 intact so the normal status line\n                // becomes RESET VC once the bounded rolling session expires.\n                suicune_roll_retry_active = false;\n                suicune_roll_autosearch_pending = false;\n                is_paused = true;\n            }\n            else if (suicune_roll_retry_countdown == 0)\n            {\n                suicune_roll_retry_active = false;\n                suicune_roll_autosearch_pending = true;\n                is_paused = true;\n            }\n        }\n\n        run_frame();\n        draw_to_screen(screenId, fb_a, stride, format);\n    }\n'''
m = replace_once(m, old_top, new_top, 'C rolling frame scheduler')
MAIN.write_text(m)

# trace.rs: auto-resume good searches, route E2/E3 into the retry scheduler,
# and turn rel40 mismatch into actual POST classification + known suffix rebind.
t = TRACE.read_text()
t = replace_once(
    t,
    '    practical_checked717: bool,\n    practical_expected40_state: u16,\n',
    '''    practical_checked717: bool,\n    practical_post_proto: u8,\n    practical_post_rot: u8,\n    practical_post_score: u16,\n    practical_rebound: bool,\n    practical_expected40_state: u16,\n''',
    'trace post fields',
)
t = replace_once(
    t,
    '            practical_checked717: false,\n            practical_expected40_state: 0,\n',
    '''            practical_checked717: false,\n            practical_post_proto: 0,\n            practical_post_rot: 0,\n            practical_post_score: 0xffff,\n            practical_rebound: false,\n            practical_expected40_state: 0,\n''',
    'trace post defaults',
)
t = replace_once(
    t,
    '        self.practical_checked717 = false;\n\n        let r = latest_pre_vblank_ring();\n',
    '''        self.practical_checked717 = false;\n        self.practical_post_proto = 0;\n        self.practical_post_rot = 0;\n        self.practical_post_score = 0xffff;\n        self.practical_rebound = false;\n\n        let r = latest_pre_vblank_ring();\n''',
    'search post reset',
)
t = replace_once(
    t,
    '            self.practical_search_error = 2;\n            pnp::request_resume();\n            return;\n',
    '            self.practical_search_error = 2;\n            pnp::request_roll_retry();\n            return;\n',
    'ERR2 rolling retry',
)
t = replace_once(
    t,
    '            self.practical_search_error = 3;\n            pnp::request_resume();\n            return;\n',
    '            self.practical_search_error = 3;\n            pnp::request_roll_retry();\n            return;\n',
    'ERR3 rolling retry',
)
t = replace_once(
    t,
    '        self.practical_search_enabled = true;\n    }\n\n    fn live_practical_lane',
    '        self.practical_search_enabled = true;\n        // v6.5.9: WAIT begins immediately; no manual R resume is needed.\n        pnp::request_resume();\n    }\n\n    fn live_practical_lane',
    'successful search auto-resume',
)
t = replace_once(
    t,
    '        self.practical_checked717 = false;\n        self.practical_expected40_state = p.expected40_state;\n',
    '''        self.practical_checked717 = false;\n        self.practical_post_proto = 0;\n        self.practical_post_rot = 0;\n        self.practical_post_score = 0xffff;\n        self.practical_rebound = false;\n        self.practical_expected40_state = p.expected40_state;\n''',
    'bind post reset',
)

bind_marker = '    fn practical_wait_monitor(&mut self, reader: &Gen2Reader) {\n'
rebind_helper = r'''    fn rebind_practical_post(&mut self, p: practical::Prediction, proto: u8, rot: u8) {
        // Keep the original Target/probe session. Only the suffix model changes.
        self.practical_lane = p.lane_id;
        self.practical_source = p.source;
        self.practical_support = p.support_weight;
        self.practical_mask = p.shiny_mask;
        self.practical_raw = p.raw;
        self.practical_miss = 0;
        self.practical_rebound = true;
        self.practical_post_proto = proto;
        self.practical_post_rot = rot;
        self.practical_expected716_state = p.expected716_state;
        self.practical_expected716_div = p.expected716_div;
        self.practical_expected717_state = p.expected717_state;
        self.practical_expected717_div = p.expected717_div;
        self.practical_checked716 = false;
        self.practical_checked717 = false;
    }

'''
t = replace_once(t, bind_marker, rebind_helper + bind_marker, 'rebind helper')

old_rel40 = '''            if rel == 40 && !self.practical_checked40 {\n                self.practical_checked40 = true;\n                if e.state != self.practical_expected40_state || e.div != self.practical_expected40_div {\n                    // v6.5: PRE->POST is not one-to-one.  Keep the normal\n                    // probe alive and turn this into a complete donor run.\n                    self.practical_miss = 1;\n                    self.practical_active = false;\n                    self.practical_candidate_valid = false;\n                }\n'''
new_rel40 = '''            if rel == 40 && !self.practical_checked40 {\n                self.practical_checked40 = true;\n                if e.state != self.practical_expected40_state || e.div != self.practical_expected40_div {\n                    // v6.5.9: identify the *actual* clean POST branch at rel40.\n                    // If an existing suffix donor matches and still predicts a\n                    // supported shiny result from the live state, rebind in-place.\n                    let post = classify_post_entries(self.entries, self.len, self.probe_target.advance);\n                    if post.valid {\n                        self.practical_post_proto = post.proto;\n                        self.practical_post_rot = post.rot40;\n                        self.practical_post_score = post.best_score;\n                    }\n                    if post.valid && post.best_score == 0 {\n                        if let Some(post_lane) = practical::lane_for_post(post.proto, post.rot40) {\n                            if let Some(pred) = practical::evaluate_post(post_lane, e.state, e.div) {\n                                self.rebind_practical_post(pred, post.proto, post.rot40);\n                            } else {\n                                // Known branch, but this actual root is not shiny-compatible.\n                                // Preserve the full probe as evidence; do not claim success.\n                                self.practical_miss = 4;\n                                self.practical_active = false;\n                                self.practical_candidate_valid = false;\n                            }\n                        } else {\n                            // Unknown branch: retain v6.5 learning fallback.\n                            self.practical_miss = 1;\n                            self.practical_active = false;\n                            self.practical_candidate_valid = false;\n                        }\n                    } else {\n                        self.practical_miss = 1;\n                        self.practical_active = false;\n                        self.practical_candidate_valid = false;\n                    }\n                }\n'''
t = replace_once(t, old_rel40, new_rel40, 'rel40 branch rebind')

save_marker = '        let _ = write!(\n            line,\n            "POSTADAPT,V65,{},{},{}\\n",\n'
branch_save = '''        let _ = write!(\n            line,\n            "BRANCH659,V659,{},{},{:02},{},{}\\n",\n            (self.practical_post_proto != 0) as u8,\n            if self.practical_post_proto == 0 { '?' as char } else { self.practical_post_proto as char },\n            self.practical_post_rot,\n            self.practical_post_score,\n            self.practical_rebound as u8\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(\n            line,\n            "POSTADAPT,V65,{},{},{}\\n",\n'''
t = replace_once(t, save_marker, branch_save, 'branch CSV telemetry')

old_status = '''        } else if self.practical_miss == 1 && self.probe_active {\n            pnp::println!("S65 LEARN 1");\n        } else if self.practical_miss != 0 {\n            pnp::println!("S65 MISS {}", self.practical_miss);\n        } else if self.practical_active {\n            pnp::println!("S64 PATH L{} W{}", self.practical_lane, self.practical_support);\n        } else if self.practical_search_error == 2 || self.practical_search_error == 3 {\n            pnp::println!("S65 RESET VC E{}", self.practical_search_error);\n'''
new_status = '''        } else if self.practical_miss == 1 && self.probe_active {\n            pnp::println!("S65 LEARN 1");\n        } else if self.practical_miss == 4 && self.probe_active {\n            pnp::println!("S659 KNOWN NO {}{:02}", self.practical_post_proto as char, self.practical_post_rot);\n        } else if self.practical_miss != 0 {\n            pnp::println!("S65 MISS {}", self.practical_miss);\n        } else if self.practical_active && self.practical_rebound {\n            pnp::println!("S659 REB {}{:02} L{} W{}", self.practical_post_proto as char, self.practical_post_rot, self.practical_lane, self.practical_support);\n        } else if self.practical_active {\n            pnp::println!("S64 PATH L{} W{}", self.practical_lane, self.practical_support);\n        } else if pnp::suicune_roll_active() {\n            pnp::println!("S659 ROLL {}/3600", pnp::suicune_roll_total());\n        } else if self.practical_search_error == 2 || self.practical_search_error == 3 {\n            pnp::println!("S65 RESET VC E{}", self.practical_search_error);\n'''
t = replace_once(t, old_status, new_status, 'v659 status lines')
TRACE.write_text(t)

print('Applied Suicune v6.5.9 rolling search + POST branch rebind patch')
