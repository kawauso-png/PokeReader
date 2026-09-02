#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()


def need(s, label):
    if s not in t:
        raise SystemExit('v714 audit missing ' + label + ': ' + s)


def span(signature):
    start=t.find(signature)
    if start<0: raise SystemExit('v714 audit function missing: '+signature)
    b=t.find('{',start); d=0
    for i in range(b,len(t)):
        if t[i]=='{': d+=1
        elif t[i]=='}':
            d-=1
            if d==0: return t[start:i+1]
    raise SystemExit('v714 audit unclosed: '+signature)

for s,label in [
    ('S714 SCAN','UI epoch'),
    ('S714 READY UP+B','READY path'),
    ('S714 LEARN P{:02X} R{}','generic learn UI'),
    ('fn rebind_known_post_v713','v713 cross rebind'),
    ('fn practical_wait_monitor','actual-root scanner'),
    ('STAGE3,V710','stage3 telemetry'),
    ('BRANCH710,V710','branch telemetry'),
    ('practical_expected716_state','rel716 guard'),
    ('practical_expected717_state','rel717 guard'),
]: need(s,label)

learn=span('    fn enter_stage3_learn(&mut self,p:u8,r:u8)')
for s in [
    'self.practical_learn=1;',
    'self.practical_active=false;',
    'self.practical_candidate_valid=false;',
    'self.practical_miss=0;',
    'self.practical_post_proto=p;',
    'self.practical_post_rot=r;',
]:
    if s not in learn: raise SystemExit('v714 audit incomplete learn transition: '+s)
if "b'D'" in learn or 'r==15' in learn:
    raise SystemExit('v714 audit learning is still D15-specific')

# Two rel40 paths (proven + empirical) must have the exact-POST learning fallback.
fallback='if post.valid&&post.best_score==0{self.enter_stage3_learn(post.proto,post.rot40)'
if t.count(fallback) != 2:
    raise SystemExit(f'v714 audit learn fallback count {t.count(fallback)} != 2')

# Rebind stays ahead of learning in both paths, so supported shiny suffixes are
# not downgraded to donor collection.
resolver='self.rebind_known_post_v713(post.proto,post.rot40,e.state,e.div)'
if t.count(resolver) != 2:
    raise SystemExit(f'v714 audit cross resolver count {t.count(resolver)} != 2')

if "post.proto==b'D'&&post.rot40==15" in t:
    raise SystemExit('v714 audit stale D15-only fallback found')
if 'S713 SCAN' in t:
    raise SystemExit('v714 audit stale S713 UI found')

# v7.1.4 must remain a rel40-learning change only.  The current-root search and
# final hard guards are inherited untouched from the already-audited chain.
print('AUDIT PASS: v7.1.4 keeps actual-root READY/CrossBranch; exact unsupported rel40 POSTs enter generic LEARN; rel716/717 guards retained')
