#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/practical.rs')
t=Path('reader_core/src/crystal/trace.rs')
m=Path('3gx/sources/main.c')
ps=p.read_text(); ts=t.read_text(); ms=m.read_text()

old='''    for i in 0..5usize{\n        let mut st=pre;let mut q=[0u8;3];'''
new='''    for i in 0..5usize{\n        // v7.3.8: do not count the source-primary deep profile twice.\n        // Several hardware donors have a primary profile identical to one of\n        // DEEP_A/DEEP_S; counting both made one physical hypothesis appear as\n        // independent multi-profile support.\n        if DEEP_A[i] == l.primary_a && DEEP_S[i] == l.primary_s { continue; }\n        let mut st=pre;let mut q=[0u8;3];'''
# Only patch the v737 adaptive evaluator occurrence.  Earlier historical evaluators
# intentionally retain their original behavior.
pos=ps.index('pub fn evaluate_adaptive_bucket(')
sub=ps[pos:]
assert old in sub, 'adaptive deep loop anchor missing'
sub=sub.replace(old,new,1)
ps=ps[:pos]+sub

ts=ts.replace('S737 A-EPOCH SCAN','S738 A-EPOCH SCAN')
ts=ts.replace('S737 CONF SHINY SCAN','S738 CONF SHINY SCAN')
ts=ts.replace('S737 SHINY LOCK','S738 SHINY LOCK')
ts=ts.replace('BUCKET737,V737,','BUCKET738,V738,')
ms=ms.replace('S737','S738')

p.write_text(ps);t.write_text(ts);m.write_text(ms)
print('applied v7.3.8 deduplicated confidence support')
