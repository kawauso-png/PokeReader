#!/usr/bin/env python3
from pathlib import Path

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

p = PRACTICAL.read_text()
p = replace_once(
    p,
    'pub const SEARCH_HORIZON: u32 = 12000;\npub const MAX_SEARCH_CANDIDATES: usize = 8;\n',
    'pub const SEARCH_HORIZON: u32 = 12000;\n// v6.6.0 trial mode: keep a generous release margin after Y+DOWN.\npub const MIN_SEARCH_LEAD: u32 = 180;\npub const MAX_SEARCH_CANDIDATES: usize = 8;\n',
    'minimum search lead',
)
PRACTICAL.write_text(p)

h = HOOK.read_text()
h = replace_once(
    h,
    'pub fn request_resume() {\n    unsafe { bindings::host_request_resume() }\n}\n',
    '''pub fn request_resume() {\n    unsafe { bindings::host_request_resume() }\n}\n\n/// Resume only after every physical command key has been released.\n/// This is the safe transition from frozen Y+DOWN search into live WAIT.\npub fn request_release_resume() {\n    unsafe { bindings::host_request_release_resume() }\n}\n''',
    'Rust release-resume wrapper',
)
HOOK.write_text(h)

b = BIND.read_text()
b = replace_once(
    b,
    '    pub fn host_request_pause();\n    pub fn host_request_resume();\n',
    '    pub fn host_request_pause();\n    pub fn host_request_resume();\n    pub fn host_request_release_resume();\n',
    'release-resume binding declaration',
)
b = replace_once(
    b,
    '    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_request_resume() {}\n',
    '    pub extern "C" fn host_request_pause() {}\n    #[no_mangle]\n    pub extern "C" fn host_request_resume() {}\n    #[no_mangle]\n    pub extern "C" fn host_request_release_resume() {}\n',
    'release-resume test stub',
)
BIND.write_text(b)

m = MAIN.read_text()
m = replace_once(
    m,
    'static u32 trace_save_req = 0;\n',
    '''static u32 trace_save_req = 0;\n\n// v6.6.0: Rust can request a safe WAIT/reset resume while the search hotkey\n// is still held. No VC frame is released until the physical command chord is\n// completely clear.\nstatic bool suicune_release_resume_pending = false;\n''',
    'C release resume state',
)
m = replace_once(
    m,
    '''void host_request_resume(void)\n{\n    is_paused = false;\n    fixed_frames_remaining = 0;\n    fixed_run_pending = false;\n}\n''',
    '''void host_request_resume(void)\n{\n    suicune_release_resume_pending = false;\n    is_paused = false;\n    fixed_frames_remaining = 0;\n    fixed_run_pending = false;\n}\n\nvoid host_request_release_resume(void)\n{\n    // Keep the VC frozen. The bottom-screen pause loop releases it only after\n    // the command chord is physically clear.\n    suicune_release_resume_pending = true;\n    fixed_frames_remaining = 0;\n    fixed_run_pending = false;\n}\n''',
    'C release resume callback',
)
m = replace_once(
    m,
    '''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if ((held & (KEY_Y | KEY_B)) != (KEY_Y | KEY_B))\n''',
    '''        u32 just_pressed = host_just_pressed();\n        u32 held = get_current_keys();\n\n        if (suicune_release_resume_pending)\n        {\n            const u32 release_block_keys = KEY_A | KEY_B | KEY_X | KEY_Y |\n                KEY_DUP | KEY_DDOWN | KEY_DLEFT | KEY_DRIGHT |\n                KEY_L | KEY_R | KEY_START | KEY_SELECT;\n            if ((held & release_block_keys) == 0)\n            {\n                suicune_release_resume_pending = false;\n                is_paused = false;\n                break;\n            }\n            svcSleepThread(1000000);\n            continue;\n        }\n\n        if ((held & (KEY_Y | KEY_B)) != (KEY_Y | KEY_B))\n''',
    'pause-loop release gate',
)
MAIN.write_text(m)

t = TRACE.read_text()
t = replace_once(
    t,
    '            self.practical_search_error = 2;\n            pnp::request_resume();\n            return;\n',
    '            self.practical_search_error = 2;\n            pnp::request_release_resume();\n            return;\n',
    'ERR2 release-gated resume',
)
t = replace_once(
    t,
    '        for step in 1..=practical::SEARCH_HORIZON {\n            practical::normal_step(&mut st, &mut div, &mut ai, &mut si);\n            let future_rot = rot.wrapping_add((step & 15) as u8) & 15;\n',
    '        for step in 1..=practical::SEARCH_HORIZON {\n            practical::normal_step(&mut st, &mut div, &mut ai, &mut si);\n            if step < practical::MIN_SEARCH_LEAD { continue; }\n            let future_rot = rot.wrapping_add((step & 15) as u8) & 15;\n',
    'minimum lead evaluation gate',
)
t = replace_once(
    t,
    '            self.practical_search_error = 3;\n            pnp::request_resume();\n            return;\n',
    '            self.practical_search_error = 3;\n            pnp::request_release_resume();\n            return;\n',
    'ERR3 release-gated resume',
)
t = replace_once(
    t,
    '        self.practical_search_enabled = true;\n    }\n\n    fn live_practical_lane',
    '''        self.practical_search_enabled = true;\n        // Y+DOWN is now one action. C waits for physical release, then WAIT.\n        pnp::request_release_resume();\n    }\n\n    fn live_practical_lane''',
    'successful search auto-WAIT',
)
old_rel40 = '''            if rel == 40 && !self.practical_checked40 {\n                self.practical_checked40 = true;\n                if e.state != self.practical_expected40_state || e.div != self.practical_expected40_div {\n                    // v6.5: PRE->POST is not one-to-one.  Keep the normal\n                    // probe alive and turn this into a complete donor run.\n                    self.practical_miss = 1;\n                    self.practical_active = false;\n                    self.practical_candidate_valid = false;\n                }\n'''
new_rel40 = '''            if rel == 40 && !self.practical_checked40 {\n                self.practical_checked40 = true;\n                if e.state != self.practical_expected40_state || e.div != self.practical_expected40_div {\n                    // PRE is not one-to-one and POST proto/rot alone is also\n                    // ambiguous. Do not guess/rebind: this donor branch lost.\n                    self.practical_fail(1);\n                    return;\n                }\n'''
t = replace_once(t, old_rel40, new_rel40, 'rel40 conservative branch fail')
t = replace_once(
    t,
    '''        let _ = write!(\n            line,\n            "POSTADAPT,V65,{},{},{}\\n",\n            self.practical_miss,\n            self.practical_active as u8,\n            self.probe_session as u8\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n''',
    '''        let _ = write!(\n            line,\n            "POSTADAPT,V65,{},{},{}\\n",\n            self.practical_miss,\n            self.practical_active as u8,\n            self.probe_session as u8\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n        let _ = write!(\n            line,\n            "TRIAL,V660,{},{},{},{}\\n",\n            self.practical_miss,\n            self.practical_checked40 as u8,\n            self.practical_checked716 as u8,\n            self.practical_checked717 as u8\n        );\n        pnp::trace_file_write(line.as_bytes());\n        line.clear();\n''',
    'v660 trial telemetry',
)
t = replace_once(t, '"S64 WAIT {}/{} +{}"', '"S660 WAIT {}/{} +{}"', 'WAIT status')
t = replace_once(t, 'pnp::println!("S64 WAIT END");', 'pnp::println!("S660 WAIT END");', 'WAIT end status')
t = replace_once(
    t,
    'pnp::println!("S64 READY L{} W{} {:04X}", self.practical_lane, self.practical_support, self.practical_raw);',
    'pnp::println!("S660 READY UP+B L{} W{} {:04X}", self.practical_lane, self.practical_support, self.practical_raw);',
    'READY status',
)
t = replace_once(
    t,
    '''        } else if self.practical_miss == 1 && self.probe_active {\n            pnp::println!("S65 LEARN 1");\n        } else if self.practical_miss != 0 {\n            pnp::println!("S65 MISS {}", self.practical_miss);\n        } else if self.practical_active {\n            pnp::println!("S64 PATH L{} W{}", self.practical_lane, self.practical_support);\n        } else if self.practical_search_error == 2 || self.practical_search_error == 3 {\n            pnp::println!("S65 RESET VC E{}", self.practical_search_error);\n        } else if self.practical_search_error != 0 {\n            pnp::println!("S64 ERR {} K{}", self.practical_search_error, self.practical_search_skipped);\n        } else {\n            pnp::println!("S64 OFF");\n''',
    '''        } else if self.practical_miss == 1 {\n            pnp::println!("S660 RETRY B40 R>RESET");\n        } else if self.practical_miss == 2 {\n            pnp::println!("S660 RETRY B716 R>RESET");\n        } else if self.practical_miss == 3 {\n            pnp::println!("S660 RETRY B717 R>RESET");\n        } else if self.practical_miss != 0 {\n            pnp::println!("S660 RETRY M{} R>RESET", self.practical_miss);\n        } else if self.practical_active {\n            pnp::println!("S660 PATH L{} W{}", self.practical_lane, self.practical_support);\n        } else if self.practical_search_error == 2 || self.practical_search_error == 3 {\n            pnp::println!("S660 RESET VC E{}", self.practical_search_error);\n        } else if self.practical_search_error != 0 {\n            pnp::println!("S660 ERR {} K{}", self.practical_search_error, self.practical_search_skipped);\n        } else {\n            pnp::println!("S660 OFF");\n''',
    'trial status block',
)
TRACE.write_text(t)

print('Applied Suicune v6.6.0 conservative branch-trial patch')
