#!/usr/bin/env python3
"""Reconstruct reviewed source payload, verify its digest, and apply to v7100."""
import base64, hashlib, json, zlib
from pathlib import Path
raw=zlib.decompress(base64.b64decode(Path('v7110_payload.b64').read_text()))
assert hashlib.sha256(raw).hexdigest()=='01b95f5ad94ae3853505eeb669b128085ee009e410052b249511386c2ee3b6e2'
files=json.loads(raw)
assert set(files)=={'apply_suicune_v7110.py','hunt_v7110.rs','hunt_v7110_model.b64'}
for name,text in files.items(): Path(name).write_text(text)
import apply_suicune_v7110 as patch
patch.apply(Path('.'))
p=Path('reader_core/src/crystal/trace.rs');t=p.read_text()
old='    pub fn start_practical_scan(&mut self, _reader: &Gen2Reader) {\n'
assert t.count(old)==1
t=t.replace(old,old+'''        if unsafe { H7110_ON } {
            self.stop();
            self.reset();
            self.probe_session=false;
            self.probe_active=false;
            self.probe_result=None;
        }
''',1)
assert t.count('STALLPHASE,V7100,')==1
t=t.replace('STALLPHASE,V7100,','STALLPHASE,V7110,',1)
p.write_text(t)
# These guards are source-level invariants, not hardware tests.
assert 'const V797_FORCE_FINAL_DV_VALIDATION: bool = true;' in t
assert 'H7110_ON' in t and 'HUNT,V7110' in t
assert 'const u32 wanted = 14U' in Path('3gx/sources/main.c').read_text()
assert 'JOY_HJOYPAD_DOWN' in Path('reader_core/src/crystal/hook.rs').read_text()
print('V7110_GENERATED_OK')
