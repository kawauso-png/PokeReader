#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v797 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

needle = "static mut V796_JPRED_MAX10: i32 = 0;\n"
insert = """static mut V796_JPRED_MAX10: i32 = 0;

// v7.9.7 validation mode: never abort at DV-2 solely because the exact-tail
// union contains no shiny raw. Continue native execution to the actual DV write
// so every blind J prediction has final-DV ground truth.
const V797_FORCE_FINAL_DV_VALIDATION: bool = true;
static mut V797_TAIL_VALID: bool = false;
static mut V797_TAIL_CANDIDATES: u8 = 0;
static mut V797_TAIL_SHINY_COUNT: u8 = 0;
static mut V797_CONTINUED_NONSHINY: bool = false;
"""
t = rep(t, needle, insert, 'globals')

old_abort = """                    if tail.shiny_count == 0 {
                        // v7.8.1 hard negative gate: all currently validated
                        // route3+route4 exact candidates are non-shiny. Save
                        // this aborted trace and pause before any DV frame.
                        self.practical_miss = 14;
                        self.practical_terminal_advance = rng_advance();
                        self.practical_active = false;
                        self.probe_active = false;
                        endpoint_fast_tail_stop();
                        self.state = TraceState::Done;
                        self.save();
                        pnp::request_pause();
                        return;
                    }
"""
new_abort = """                    unsafe {
                        V797_TAIL_VALID = true;
                        V797_TAIL_CANDIDATES = tail.candidate_count;
                        V797_TAIL_SHINY_COUNT = tail.shiny_count;
                    }
                    if tail.shiny_count == 0 {
                        if V797_FORCE_FINAL_DV_VALIDATION {
                            // v7.9.7 validation: preserve the hard-negative
                            // diagnosis, but do NOT terminate at DV-2. Let the
                            // game execute its native final Random/DV write so
                            // this blind trace has actual-DV ground truth.
                            unsafe { V797_CONTINUED_NONSHINY = true; }
                        } else {
                            self.practical_miss = 14;
                            self.practical_terminal_advance = rng_advance();
                            self.practical_active = false;
                            self.probe_active = false;
                            endpoint_fast_tail_stop();
                            self.state = TraceState::Done;
                            self.save();
                            pnp::request_pause();
                            return;
                        }
                    }
"""
t = rep(t, old_abort, new_abort, 'DV-2 hard-negative bypass')

anchor_reset = """        unsafe {
            for i in 0..V792_AUDIO_PRE_LEN {
"""
repl_reset = """        unsafe {
            V797_TAIL_VALID = false;
            V797_TAIL_CANDIDATES = 0;
            V797_TAIL_SHINY_COUNT = 0;
            V797_CONTINUED_NONSHINY = false;
            for i in 0..V792_AUDIO_PRE_LEN {
"""
t = rep(t, anchor_reset, repl_reset, 'probe reset')

needle_csv = """        line.clear();
        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");
"""
insert_csv = """        line.clear();
        let _ = write!(line, "\\nkbranch,version,valid,actual_j_a,actual_j_s,cycles27,cycles28,k27,k28,post1_rel,pre_ap4,post1_ap4,ctx_pc,ctx_div,ctx_sub,ctx_bank,tail_valid,tail_candidates,tail_shiny,continued_nonshiny,final_result\\n");
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        unsafe {
            let kval = (self.early_pre.valid != 0 && self.early_post1.valid != 0 && V796_JPRED_VALID) as u8;
            let k27 = V796_JPRED_C27 as i32 - self.early_j_a;
            let k28 = V796_JPRED_C28 as i32 - self.early_j_a;
            let post1_rel = self.early_post1.advance.wrapping_sub(self.probe_target.advance);
            let final_result = self.probe_result.is_some() as u8;
            let _ = write!(line, "KBRANCH,V797,{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:02X},{:02X},{:02X},{},{},{},{},{}\\n",
                kval, self.early_j_a, self.early_j_s, V796_JPRED_C27, V796_JPRED_C28,
                k27, k28, post1_rel, self.early_pre.ap4, self.early_post1.ap4,
                V790_CPU_CTX_PC, V790_CPU_CTX_DIV, V790_CPU_CTX_SUB, V790_CPU_CTX_BANK,
                V797_TAIL_VALID as u8, V797_TAIL_CANDIDATES, V797_TAIL_SHINY_COUNT,
                V797_CONTINUED_NONSHINY as u8, final_result);
        }
        pnp::trace_file_write(line.as_bytes());

        line.clear();
        let _ = write!(line, "\\naudio_pre,version,valid,target,base,len,audio_hex\\n");
"""
t = rep(t, needle_csv, insert_csv, 'KBRANCH csv')

t = rep(t,
    'STALLPHASE,V796,rel0-40+vblankirq+cpuctx84+audiopre+jpred-sd',
    'STALLPHASE,V797,rel0-40+vblankirq+cpuctx84+audiopre+jpred-sd+kbranch+finaldv',
    'version marker')
t = rep(t, 'S796 JPRED READY', 'S797 JPRED READY', 'overlay ready')
t = rep(t, 'PRESS UP BLIND', 'PRESS UP BLIND + FINAL DV', 'overlay instruction')

T.write_text(t)
print('Applied v7.9.7 K-branch + final-DV validation: DV-2 hard-negative is telemetry-only; native final DV always captured')
