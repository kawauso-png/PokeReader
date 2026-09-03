from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
t=T.read_text()
old='''        if !self.practical_scan_enabled||!self.practical_live_scan||self.probe_session||self.practical_active||self.practical_candidate_valid{return}\n'''
new='''        // If the previous +4096 ADV window contained no candidate, do not\n        // recompute the same overlapping window at every A/r10. The marker is\n        // the first ADV not covered by the previous window.\n        if self.practical_live_found_lane==0&&self.practical_live_found_advance!=0&&cur<self.practical_live_found_advance{return}\n        if !self.practical_scan_enabled||!self.practical_live_scan||self.probe_session||self.practical_active||self.practical_candidate_valid{return}\n'''
if old not in t:raise SystemExit('monitor guard anchor missing')
t=t.replace(old,new,1)
old='''        let Some(fp)=practical::select_future_weighted_a10(bucket,reader.rng_state(),measured_div(),ai,si)else{return};\n'''
new='''        let Some(fp)=practical::select_future_weighted_a10(bucket,reader.rng_state(),measured_div(),ai,si)else{\n            self.practical_live_found_advance=cur.wrapping_add((practical::FUTURE_ROOTS_V761 as u32)*16);\n            return\n        };\n'''
if old not in t:raise SystemExit('future none anchor missing')
t=t.replace(old,new,1)
T.write_text(t)
