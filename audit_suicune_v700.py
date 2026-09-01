#!/usr/bin/env python3
from pathlib import Path
import ast, base64, zlib

P = Path('reader_core/src/crystal/practical.rs').read_text()
T = Path('reader_core/src/crystal/trace.rs').read_text()
errors=[]
def need(c,m):
    if not c: errors.append(m)

need('pub fn evaluate_exact' in P,'missing evaluate_exact')
need('pub fn evaluate_post_exact' in P,'missing evaluate_post_exact')
need('cadence_correction' in P,'missing cadence correction')
need("raw_a: &'static [u8; 730]" in P and "raw_s: &'static [u8; 730]" in P,'missing raw paths')
need('source_ai:' in P and 'source_si:' in P,'missing donor indices')
need('for rel in 0..730usize' in P,'root exact range wrong')
need('for rel in 41..730usize' in P,'POST exact range wrong')
need('evaluate_post_unique' not in P,'nominal POST evaluator remains')
need('lane_for_post_unique' in P,'unique POST gate lost')

ms=T.find('    fn practical_wait_monitor(&mut self, reader: &Gen2Reader)')
me=T.find('\n    fn ',ms+10)
monitor=T[ms:me]
need(ms>=0,'monitor missing')
need('let Some(ai_raw) = add_div_tracker().index() else' in monitor,'A index Option gate missing')
need('let Some(si_raw) = sub_div_tracker().index() else' in monitor,'S index Option gate missing')
need('unwrap_or(0)' not in monitor,'unknown index aliases zero in monitor')
need('practical::evaluate_exact(lane_id, state, div, ai, si)' in monitor,'monitor not exact')
need('practical::evaluate(lane_id, state, div)' not in monitor,'nominal evaluator gates first')
need('full_index_window_safe' not in monitor,'v6.9 reject gate remains')
need('normal_step(' not in monitor,'future transport reintroduced')
need('SEARCH_HORIZON' not in monitor,'future horizon reintroduced')

need('practical::evaluate_post_exact(' in T,'rel40 exact rebind missing')
need('practical::evaluate_post_unique(' not in T,'rel40 nominal rebind remains')
need('practical::lane_for_post_unique(post.proto, post.rot40)' in T,'unique POST gate lost')
need('rel == 716' in T and 'practical_expected716_state' in T and 'practical_expected716_div' in T,'B716 guard lost')
need('rel == 717' in T and 'practical_expected717_state' in T and 'practical_expected717_div' in T,'B717 guard lost')
need('S658 TEST' in T,'S658 FastValidate lost')
for x in ['S700 SCAN','S700 READY UP+B','S700 REB','S700 RETRY B40','S700 RETRY B716','S700 RETRY B717','BRANCH700,V700']:
    need(x in T,f'missing {x}')
need('practical_live_index_wait' in T,'index-wait telemetry missing')
need('practical_live_exact_eval' in T,'exact-eval telemetry missing')
need('S690 ' not in T,'active S690 status remains')

payload=''.join(Path(f'apply_suicune_practical_shiny_v64_payload_{i}.txt').read_text().strip() for i in (0,1))
decoded=zlib.decompress(base64.b85decode(payload.encode())).decode('utf-8')
tree=ast.parse(decoded)
lanes=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='LANES' for x in n.targets))
SOURCE={87:(1866,1153),94:(1023,310),95:(9878,9165),89:(3484,10278),96:(2269,9063),86:(10679,1089)}
EX={0x0008,0x0009,0x0562,0x0563,0x22b5,0x22b6}
crossing=[]
for lid,src,proto,rot,ah,sh in lanes:
    need(len(bytes.fromhex(ah))==730 and len(bytes.fromhex(sh))==730,f'lane {lid} payload length')
    ai,si=SOURCE[src]
    if any(((ai+r)&0x3fff) in EX or ((si+r)&0x3fff) in EX for r in range(730)): crossing.append(src)
need(set(crossing)=={86,87,94},f'unexpected donor exception set {crossing}')
for src,(ai,si) in SOURCE.items():
    need(f'source_ai: {ai},' in P and f'source_si: {si},' in P,f'missing source index pair {src}')

if errors:
    print('v7.0 AUDIT FAIL')
    for e in errors: print(' -',e)
    raise SystemExit(1)
print('v7.0 AUDIT PASS: Exact-Index LiveRoot, explicit IDX WAIT, donor normalization, exact POST rebind, hard guards preserved')
