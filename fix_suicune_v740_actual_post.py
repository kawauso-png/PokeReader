#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/trace.rs')
t=p.read_text()
old='''        line.clear();\n        let actual_raw=self.probe_result.map(|x|x.raw_dv).unwrap_or(0);\n        let actual_route=self.probe_result.map(|x|x.route).unwrap_or(0);\n        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_slot,actual_slot,post_proto,post_rot,raw_dv,route,freeze_delta\\nSWEEP,V740,{},{},{},{},{},{},{:04X},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&7,\n            if rpm.period!=0{((rpm.actual/rpm.period)&7)as u32}else{255},\n            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,\n            actual_raw,actual_route,self.sweep_freeze_delta);'''
new='''        line.clear();\n        let actual_raw=self.probe_result.map(|x|x.raw_dv).unwrap_or(0);\n        let actual_route=self.probe_result.map(|x|x.route).unwrap_or(0);\n        let sweep_post=classify_post_entries(self.entries,self.len,self.probe_target.advance);\n        let _=write!(line,\n            "\\nslot_sweep,version,target_bucket,actual_bucket,wanted_slot,actual_slot,post_proto,post_rot,post_score,raw_dv,route,freeze_delta\\nSWEEP,V740,{},{},{},{},{},{},{},{:04X},{},{}\\n",\n            self.sweep_target_bucket,self.bucket_current,rpm.slot&7,\n            if rpm.period!=0{((rpm.actual/rpm.period)&7)as u32}else{255},\n            if sweep_post.valid{sweep_post.proto as char}else{'?'},sweep_post.rot40,sweep_post.best_score,\n            actual_raw,actual_route,self.sweep_freeze_delta);'''
if old not in t: raise SystemExit('v740 actual POST fix anchor missing')
t=t.replace(old,new,1)
p.write_text(t)
print('v7.4.0 sweep CSV now uses actual POST fingerprint classification')
