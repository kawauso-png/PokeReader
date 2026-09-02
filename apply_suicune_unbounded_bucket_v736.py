#!/usr/bin/env python3
from pathlib import Path

P=Path('reader_core/src/crystal/practical.rs')
T=Path('reader_core/src/crystal/trace.rs')
M=Path('3gx/sources/main.c')

p=P.read_text(); t=T.read_text(); m=M.read_text()

old='''pub fn adaptive_bucket_radius(steps:u32)->u8 {
    if steps < 4096 { 4 }
    else if steps < 12288 { 8 }
    else if steps < 24576 { 16 }
    else { 128 }
}'''
new='''pub fn adaptive_bucket_radius(steps:u32)->u8 {
    // v7.3.6: `steps` counts RNG-advance changes, not released display frames.
    // Hardware v7.3.5 reached the 200k neutral-frame watchdog around N23574,
    // so the old N24576 full-range threshold was effectively unreachable.
    // Widen sooner while preserving a conservative anchor-neighborhood stage.
    if steps < 2048 { 4 }
    else if steps < 6144 { 8 }
    else if steps < 12288 { 16 }
    else { 128 }
}'''
if old not in p: raise SystemExit('v736: adaptive radius block not found')
p=p.replace(old,new,1)

oldm='''                if (suicune_root_lock_steps >= SUICUNE_ROOT_LOCK_MAX_STEPS)
                {
                    suicune_root_lock_failed = true;
                    suicune_root_lock_active = false;
                    continue;
                }'''
newm='''                if (suicune_root_lock_steps >= SUICUNE_ROOT_LOCK_MAX_STEPS)
                {
                    // v7.3.6: watchdog rollover, never silently terminate the
                    // frozen-root search.  v7.3.5 stopped here while the Rust UI
                    // still said PAUSE SHINY SCAN.  Keep the accumulated Rust
                    // bucket_scan_steps/radius and continue neutral stepping.
                    suicune_root_lock_steps = 0;
                    suicune_root_lock_failed = false;
                }'''
if oldm not in m: raise SystemExit('v736: root-lock watchdog block not found')
m=m.replace(oldm,newm,1)

# Make the build unmistakable on hardware/CSV.
t=t.replace('BUCKET735,V735,','BUCKET736,V736,')
t=t.replace('S735 A-EPOCH SCAN','S736 A-EPOCH SCAN')
t=t.replace('S735 SHINY LOCK','S736 SHINY LOCK')
t=t.replace('S735 PAUSE SHINY SCAN','S736 PAUSE SHINY SCAN')

P.write_text(p); T.write_text(t); M.write_text(m)
print('v7.3.6 applied: early full-range bucket widening + non-terminating neutral watchdog rollover')
