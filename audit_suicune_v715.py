#!/usr/bin/env python3
from pathlib import Path

H=Path('reader_core/src/crystal/hook.rs')
T=Path('reader_core/src/crystal/trace.rs')
h=H.read_text(); t=T.read_text()

def need(text, marker, label):
    if marker not in text:
        raise SystemExit(f'v715 AUDIT FAIL missing {label}: {marker}')

for m in [
    'pub const ENDPOINT_FAST_SIG_MAX: usize = 4;',
    'pub struct EndpointFastSig',
    'endpoint_fast_tail_sig_count()',
    'endpoint_fast_tail_sig(index: usize)',
    'r1: regs[1]', 'r5: regs[5]', 'r12: regs[12]', 'lr: regs[13]', 'host_pc: regs[14]',
]: need(h,m,m)
for m in [
    'FASTTAIL715,V715',
    'fasttail715_call,index,r1,r2,r3,r4,r5,r12,lr,host_pc',
    'S715 SCAN', 'S715 READY UP+B', 'S715 LEARN P',
    'fn rebind_known_post_v713', 'fn enter_stage3_learn',
    'practical_expected716_state', 'practical_expected717_state',
    'STAGE3,V710', 'BRANCH710,V710',
]: need(t,m,m)

# The key safety property: Random's PURETAIL branch must still return before
# any timing/emulator-state observation.  Static register copies are allowed.
start=h.find('if unsafe { ENDPOINT_FAST_TAIL } && (pc == 0x2f60 || pc == 0x2f68)')
end=h.find('        return;\n    }',start)
if start < 0 or end < 0:
    raise SystemExit('v715 AUDIT FAIL: PURETAIL block not found')
block=h[start:end]
for bad in ['reader.div(', 'rng_state(', 'system_tick(', 'pnp::read', 'read_volatile', 'gb_mem', 'capture_deep_random', 'CALL_LOG[']:
    if bad in block:
        raise SystemExit(f'v715 AUDIT FAIL: Random fast path contains {bad}')
if 'regs[' not in block or 'ENDPOINT_FAST_CALLS' not in block:
    raise SystemExit('v715 AUDIT FAIL: compact signature/counter not present in fast path')

# Do not accidentally regress the v714 learn-all behavior.
if "post.proto==b'D'&&post.rot40==15" in t:
    raise SystemExit('v715 AUDIT FAIL: D15-only LEARN guard returned')
if 'S714 SCAN' in t:
    raise SystemExit('v715 AUDIT FAIL: stale S714 SCAN UI')

print('AUDIT PASS: v7.1.5 preserves actual-root/CrossBranch/LearnAllPost and adds register-only PURETAIL fingerprint; no Random-time DIV/state/tick/emulator reads')
