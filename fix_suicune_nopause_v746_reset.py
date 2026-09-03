#!/usr/bin/env python3
from pathlib import Path
T=Path('reader_core/src/crystal/trace.rs')
F=Path('reader_core/src/crystal/frame.rs')
t=T.read_text(); f=F.read_text()

def need(c,m):
    if not c: raise SystemExit('v746 reset '+m)

if 'pub fn nopause_jtest_reset_epoch(&mut self)' not in t:
    anchor='    pub fn nopause_jtest_tick(&mut self, reader: &Gen2Reader) {'
    p=t.find(anchor); need(p>=0,'tick method missing')
    method=r'''    pub fn nopause_jtest_reset_epoch(&mut self) {
        self.stop();
        self.reset();
        self.probe_active=false;
        self.probe_session=false;
        self.probe_result=None;
        self.nptest_stage=0;
        self.nptest_last_keys=0;
        self.nptest_trigger_advance=0;
        self.nptest_trigger_state=0;
        self.nptest_trigger_div=0;
        deep_log_clear();
    }

'''
    t=t[:p]+method+t[p:]

if 'state.trace.nopause_jtest_reset_epoch();' not in f:
    old='''        (0x0101, 0x01ff) => {
            reset_rng_advance();
            1
        }'''
    new='''        (0x0101, 0x01ff) => {
            state.trace.nopause_jtest_reset_epoch();
            reset_rng_advance();
            1
        }'''
    need(old in f,'RNG reset epoch anchor missing')
    f=f.replace(old,new,1)

T.write_text(t);F.write_text(f)
print('Applied v7.4.6 NOPAUSE VC-reset epoch reset')
