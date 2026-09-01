#!/usr/bin/env python3
from pathlib import Path

path = Path("reader_core/src/crystal/trace.rs")
text = path.read_text()

old = '''        let ai_now = add_div_tracker().index().unwrap_or(0) as u32;
        let ai_validate = ai_now.wrapping_sub(pre_lag);
        for i in 0..16usize {
'''
new = '''        // v6.5.3: calibrate the 16-step DIV cadence from the observed PRE
        // window instead of trusting the tracker index at the pause boundary.
        let ai_hint = add_div_tracker().index().unwrap_or(0) as u32;
        let mut cadence_first: Option<u32> = None;
        for phase in 0..16u32 {
            let mut ok = true;
            for j in 0..16usize {
                let (_, p0) = pre_ring_sample(&r, j);
                let (_, p1) = pre_ring_sample(&r, j + 1);
                let b0 = (p0 >> 6) as u8;
                let b1 = (p1 >> 6) as u8;
                if b1.wrapping_sub(b0) != practical::normal_inc(phase.wrapping_add(j as u32)) {
                    ok = false;
                    break;
                }
            }
            if ok {
                cadence_first = Some(phase);
                break;
            }
        }
        let Some(ai_validate) = cadence_first else {
            self.practical_search_error = 2;
            return;
        };
        let cadence_current = ai_validate.wrapping_add(16).wrapping_add(pre_lag);
        let ai_now = (ai_hint & !15) | (cadence_current & 15);
        for i in 0..16usize {
'''

n = text.count(old)
if n != 1:
    raise SystemExit(f"v6.5.3 cadence autophase anchor count: {n}")
text = text.replace(old, new, 1)

if "calibrate the 16-step DIV cadence" not in text:
    raise SystemExit("v6.5.3 marker missing")

path.write_text(text)
print("Applied Suicune v6.5.3 DIV cadence autophase calibration")
