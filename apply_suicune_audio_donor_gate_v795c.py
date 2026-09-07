#!/usr/bin/env python3
from pathlib import Path

C=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
c=C.read_text(); t=T.read_text()

def rep(src,old,new,label):
    n=src.count(old)
    if n!=1: raise SystemExit(f'v795c {label}: expected 1 match, got {n}')
    return src.replace(old,new,1)

# The historical B stage was host-only and never reached Crystal. Production
# mode can therefore start the measured neutral-3F transport automatically as
# soon as the frozen shiny root is locked. Any physically held gameplay key is
# still blocked by the neutral-key guard before a VC frame is released.
old='''        if ((held & KEY_B) && !(held & KEY_Y)
            && suicune_root_lock_ready
            && !suicune_wait_up_after_b
            && !fixed_run_pending && !suicune_auto_resume_pending)
        {'''
new='''        if (suicune_root_lock_ready
            && !suicune_wait_up_after_b
            && !fixed_run_pending && !suicune_auto_resume_pending)
        {'''
c=rep(c,old,new,'automatic donor transport start')

old_ui='''        } else if self.probe_session && self.probe_active && !self.practical_active {
            pnp::println!("S732 CONTROL RUN");
'''
new_ui='''        } else if self.probe_session && self.probe_active && !self.practical_active {
            unsafe {
                if V795_DONOR_ACCEPTED {
                    pnp::println!("S795 DONOR OK RUN{}", V795_DONOR_RUN);
                    pnp::println!("POST {}/r{} J{}", V795_DONOR_POST_PROTO as char, V795_DONOR_POST_ROT, V795_DONOR_J);
                    pnp::println!("PRESS UP ONLY");
                } else {
                    pnp::println!("S795 DONOR CHECK");
                }
            }
'''
t=rep(t,old_ui,new_ui,'donor accepted UI')

C.write_text(c); T.write_text(t)
print('Applied v7.9.5c: automatic host-only donor check; user input required only for accepted physical UP')
