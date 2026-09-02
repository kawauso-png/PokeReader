#!/usr/bin/env python3

# Small host-side model of the v7.3.4 Suicune execution protocol. This is not
# an RNG accuracy test; it locks the intended input semantics against future
# pause-loop regressions.

def sampled(t, start, duration, period):
    # A held-level sampler sees B when any sample instant lands inside press.
    for x in range(0, 100, period):
        if start <= x < start + duration:
            return True
    return False

# A 10ms tap can be completely invisible to a 50ms poll for many phases.
old_hits=sum(sampled(0,s,10,50) for s in range(50))
assert old_hits < 50, old_hits
# Once UP is held, v7.3.4 polls at 1ms; every integer-ms 10ms tap is observed.
new_hits=sum(sampled(0,s,10,1) for s in range(50))
assert new_hits == 50, new_hits

# State machine: TEST is frozen. B+UP latches pending; B must be released
# before Exact2F begins. Exact frames contain UP only. After two frames the
# plugin freezes again until physical UP is released, then auto-resumes.
state='TEST'
frames=[]

def tick(up,b):
    global state
    if state=='TEST':
        if up and b:
            state='PENDING'
        return
    if state=='PENDING':
        if not b:
            state='F1'
        return
    if state=='F1':
        assert up and not b
        frames.append('UP')
        state='F2'
        return
    if state=='F2':
        assert up and not b
        frames.append('UP')
        state='RELEASE_UP'
        return
    if state=='RELEASE_UP':
        if not up:
            state='RESUMED'
        return

# Hold UP first, then B. No VC frame before B release.
tick(True,False); assert frames==[] and state=='TEST'
tick(True,True);  assert frames==[] and state=='PENDING'
tick(True,True);  assert frames==[] and state=='PENDING'
tick(True,False); assert frames==[] and state=='F1'
tick(True,False); assert frames==['UP'] and state=='F2'
tick(True,False); assert frames==['UP','UP'] and state=='RELEASE_UP'
# Continuing to hold UP intentionally stays frozen; visible movement need not
# complete until the user releases UP.
tick(True,False); assert state=='RELEASE_UP'
tick(False,False);assert state=='RESUMED'
assert frames==['UP','UP']

print(f'v7.3.4 INPUT MODEL PASS: old 50ms caught {old_hits}/50 phase-aligned 10ms taps; new 1ms caught {new_hits}/50; VC keys={frames}; resume waits for UP release')
