#!/usr/bin/env python3
from pathlib import Path
import base64, json, zlib

P=Path('reader_core/src/crystal/practical.rs')
T=Path('reader_core/src/crystal/trace.rs')

DATA_B85=r'''c-rmS%}yjY6o%n@skIkA{x>@y<R(TaLJAXQ6GlLiMKt%GQ{bP|v`yJ(piqz44WS=urbD}5eO+JvTmD+kKq|3(`?j1d=L`PfemTRh@7Av`@asGL+Kc7>?(fIj<;>upZvMq@{rZc)TEF}C>%;9MK0<?79&hgdxPAQX;qhjD=wg+VOZl(A|M}1Q6VET!i`*<{UmytWg|)(K5kUY*0V)VEPJpulf)+}GP)Z7=gTU{`42+1108fA_Kv^Te3vGqf!YdK+;SwLN@aG$RxYJ1R=SzGz{#}%INNgsikch++q6qPYxJ-bM^<QELiIs#*bR~h1^p8(OW-#$=(WiI&*@E`d8woH3!~}w{t^gpw5daCGOu&k$2?zw}0#pXR0KAHp1lS6UOdw`p2*9g2Pk_n*GH?|D0r*QHO#wQCP=F>N5P%Og@C*<pU@Nea09(LHpFkAeSD*;+1gHdn0z*I~z+|8^2qHQHfB;v3O~A<l@G4pp5D3r-s0=&-coi=Ruo;*PVg-f({B@AN0G9z2;0OQ$)`yw|bOwO{O+YAMeVHZ@WCgYYJRB;p3E-7f0iFOwfX~2X03t>L3<0r#kby1$uY#vS1wepHz$O5A1XZz~TAGNEh0j6};fYvZG_r`8g{dMEVTi!T;@R*lToFKoBLa$8ad;y5BxphcA)1hoiKhe)he~WEctB(lGr^yTM^`1D5LF3e;wr%_t*2cfhLD&^C`1#2KM_xfN+1)&iP%c;l&Az>7kE%Sk@a=2GVzrtLOdagl30i#BobmO(E_iRh$93DafCo3Xz?T~L=zGS(S@i?)?Wr&2_6`g*h)+$u@bxzo*2&ruY`w2B`Omr#1R57h$%#85(v?R;Hv}=j%TtSfQjIlR*0=6NJ1<nst`|zBE(nX1YR$ZNQfaM5@IsJP=ZPvAwY;L#3pjkR;IMoGYOTfy5?B_z1<(bw_l6p;bk>$XN{cAnr=1r5^$gzI|(>ajg15xYsRAle22m=&Dc)B&1UQ+;8rvC5^%d2n+Z75jEw{wYsRAl9BM|DfoC>jF9Dm)xSfEVX531^UNg26aHJU<2{_h_M+rF8jI9J5XvXaXY&PR|0(P3Qmw+#u@h}0+W&*wvjT;I0S~R|%fZb>eS@a5UI~orPa3C6c1vn6my#gGF#%2MIMWe1naig(afc<FPEWlngb_#GH8hZse5RHlu&yU7N0lpTEu98*(4n<?T0Q=F{EWnXy>=fWYH1-N`AR2pv95WizoBQ>5ktR-^CeF(=arze%r#qfFFRrxTm^iO298H{;`cjjL^F51=pW(0fE%5s`aQk+86%DLaH1bwa$6G};a}_-(T*EC~;1#Z774GCJs&-vP9d{Mg%vJQDa1F0;Ew6ADt8gb*QN>$DdxaZj3U_K1Z3eEJ3*6aN)bm!+X5hZ>DysOaXymV=j=zfP4_HNkyNU+(Dr)(w=o<y@<SN<-+;?9^4R;j<_9_}iR?$?ekZW~#yCM_kNYu2eaqxrj*$%gJtEgwMqOAlRSVb+bv3t)J%q+-Lt7t0$hgMO|Tt!O)&aI-rTSeOmxVeg2?kd_#z^PT#@K#Z~$0}-gt0?eR(ZF3rdkHwTiuzqv(U%E0){M;poEt?WdlYqhjiQ!6iYopn8kwVL4Zzt^v=e}nqiEc16b<}Q)bg9L5rC7UXyA{ccDGT~@JCVLkD}p+oAGerG-=_yNDC*Vh4VZuoT@CGIxn0UU-Dq#lt&9^0CWCw;S4&Myl`@E8k}gOAFfEXcSXA0D^mW<6{&WwNOu|)sdyC`Po*Mv|7<<%T9I&46{*=3Ns{oVu1NThigYJck@B=EQt>M?eoRF&Cp|Ma>EZu|XVUqgu=)Pp**4$0vj(4t=}*Kz@A&+@<8${rKGp7bd|K`upXz76<8%Ki4R3YF=ev9!9+{tqzr_uo{_}><eX4ZwhEMr<!{__m@aazahR?EX&b+r@f4}}8{uDdE'''

def need(x,m,label):
    if m not in x: raise SystemExit('v730 missing '+label+': '+m)
def rep(x,a,b,label,count=1):
    n=x.count(a)
    if n!=count: raise SystemExit(f'v730 {label}: expected {count}, got {n}')
    return x.replace(a,b)

def upd(st,a,s):
    ra,rs=(st>>8)&255,st&255; z=ra+(a&255); c=1 if z>255 else 0
    return ((z&255)<<8)|((rs-(s&255)-c)&255)
def apply(st,ba,bs,a,s,end):
    for i in range(end+1): st=upd(st,(ba+a[i])&255,(bs+s[i])&255)
    return st
def table(raw,end): return [sum(((b+x)&255) for x in raw[:end+1]) for b in range(256)]
def arr(n,v): return 'const '+n+':[u32;256]=['+','.join(map(str,v))+'];\n'
def r4(st,ba,bs,A,S):
    q=[]
    for a,s in zip(A,S): st=upd(st,(ba+a)&255,(bs+s)&255); q.append(st&255)
    return q

D=json.loads(zlib.decompress(base64.b85decode(DATA_B85)).decode())
if [x['n'] for x in D] != [102,103,104]: raise SystemExit('v730 donor payload ids')
OLD_A=[183,185,191,193]; OLD_S=[183,186,191,193]
ALT_A=[184,186,192,194]; ALT_S=[184,186,192,194]
DEEP_A0=[183,189,191]; DEEP_S0=[183,189,191]
expect={102:(0x8D0A,0x6F78,0x8364,0x7C64,0xFD7E),103:(0x8355,0x55CF,0x72B2,0xDC41,0xBE37),104:(0x05AC,0x33B7,0xB832,0x8C56,0x2000)}
for d in D:
    st=int(d['target_state'],16); div=int(d['target_div'],16); ba,bs=div>>8,div&255; term=d['offset']-1
    e40,e716,e717,epre,eraw=expect[d['n']]
    if apply(st,ba,bs,d['a'],d['s'],40)!=e40: raise SystemExit(f"{d['n']} rel40 regression")
    if apply(st,ba,bs,d['a'],d['s'],716)!=e716: raise SystemExit(f"{d['n']} rel716 regression")
    if apply(st,ba,bs,d['a'],d['s'],717)!=e717: raise SystemExit(f"{d['n']} rel717 regression")
    pre=apply(st,ba,bs,d['a'],d['s'],term)
    if pre!=epre: raise SystemExit(f"{d['n']} terminal root {pre:04X}")
    la=(ba+d['a'][term])&255; ls=(bs+d['s'][term])&255
    if d['route']==4:
        q=r4(pre,la,ls,ALT_A,ALT_S); got=(q[2]<<8)|q[3]
        if q[0]<0xC0 or got!=eraw: raise SystemExit(f"{d['n']} alt-route4 raw {got:04X}")
    else:
        q=r4(pre,la,ls,DEEP_A0,DEEP_S0); got=(q[1]<<8)|q[2]
        if q[0]>=0xC0 or got!=eraw: raise SystemExit(f"{d['n']} route3-p1 raw {got:04X}")
# Existing 0101 must keep the old route4 tail.
q=r4(0xADB8,0x04,0x04,OLD_A,OLD_S)
if q[0]<0xC0 or ((q[2]<<8)|q[3])!=0x7AB4: raise SystemExit('0101 old-route4 regression')

p=P.read_text(); t=T.read_text()
need(p,'const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=5;','v710 empirical bank')
need(p,'const EMP_R4_A:[u8;4]=[183,185,191,193]; const EMP_R4_S:[u8;4]=[183,186,191,193];','route4 base')
need(p,'pub fn evaluate_empirical_post','v713 empirical rel40 evaluator')
need(p,'pub fn empirical_lane_for_post_unique_global','v720 POST helper')
need(t,'fn rebind_known_post_v720','v720 rel40 resolver')
need(t,'S720 SCAN','v720 UI')
need(t,'S720 TEST UP+B','UP+B UI')

p=rep(p,'const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=5;','const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=8;','EMP_COUNT')
p=rep(p,'const EMP_R4_A:[u8;4]=[183,185,191,193]; const EMP_R4_S:[u8;4]=[183,186,191,193];',
'''const EMP_R4_A:[u8;4]=[183,185,191,193]; const EMP_R4_S:[u8;4]=[183,186,191,193];
const EMP_R4_ALT_A:[u8;4]=[184,186,192,194]; const EMP_R4_ALT_S:[u8;4]=[184,186,192,194];
#[inline] fn emp_r4_step(source:u16,j:usize)->(u8,u8){if source==102||source==103{(EMP_R4_ALT_A[j],EMP_R4_ALT_S[j])}else{(EMP_R4_A[j],EMP_R4_S[j])}}''','route4 selector')

defs=''
for ix,d in enumerate(D,6):
    term=d['offset']-1
    for n,raw,end in [('FA',d['a'],term),('FS',d['s'],term),('A40',d['a'],40),('S40',d['s'],40),('A716',d['a'],716),('S716',d['s'],716)]: defs+=arr(f'E{ix}_{n}',table(raw,end))
p=rep(p,'const EMP_LANES:[EmpLane;EMP_COUNT]=[\n',defs+'const EMP_LANES:[EmpLane;EMP_COUNT]=[\n','new donor tables')
entries=''
for ix,d in enumerate(D,6):
    a,s=d['a'],d['s']; term=d['offset']-1
    entries += f"EmpLane{{id:{100+ix},source:{d['n']},pre_proto:b'{d['pp']}',pre_rot:{d['pr']},post_proto:b'{d['op']}',post_rot:{d['or']},route:{d['route']},full_a:&E{ix}_FA,full_s:&E{ix}_FS,p40_a:&E{ix}_A40,p40_s:&E{ix}_S40,p716_a:&E{ix}_A716,p716_s:&E{ix}_S716,o40a:{a[40]},o40s:{s[40]},o716a:{a[716]},o716s:{s[716]},o717a:{a[717]},o717s:{s[717]},last_a:{a[term]},last_s:{s[term]}}},\n"
anchor='];\nfn emp_lane'
pos=p.index(anchor,p.index('const EMP_LANES'))
p=p[:pos]+entries+p[pos:]

emp_lane_anchor="fn emp_lane(id:u8)->Option<&'static EmpLane>{if id<EMP_FIRST_ID{return None} EMP_LANES.get((id-EMP_FIRST_ID)as usize)}\n"
need(p,emp_lane_anchor,'emp_lane')
p=p.replace(emp_lane_anchor,emp_lane_anchor+'''#[inline] fn empirical_trusted_source(source:u16)->bool{source!=97}
pub fn empirical_first_id()->u8{EMP_FIRST_ID}
pub fn empirical_count_u8()->u8{EMP_COUNT as u8}
pub fn proven_lane_count()->u8{LANE_COUNT as u8}
pub fn known_pre_rot_count(proto:u8)->u8{let mut n=0u8;for r in 0..16u8{if lane_for_pre(proto,r).is_some()||empirical_has_pre(proto,r){n=n.saturating_add(1)}}n}
''',1)

# Source0097 is retained for observation/identity, but its actual 241F terminal
# is outside the current route3 terminal support bank. Never auto-target it.
old='if !empirical_window_safe(ai,si){return None} let l=emp_pre(proto,rot)?;let av=(div>>8)as u8;let sv=div as u8;'
new='if !empirical_window_safe(ai,si){return None} let l=emp_pre(proto,rot)?;if !empirical_trusted_source(l.source){return None}let av=(div>>8)as u8;let sv=div as u8;'
p=rep(p,old,new,'matched empirical trust gate')
# Route4 must be selected per empirical donor family, both from Target and rel40.
old_loop='for j in 0..4{st=upd(st,la.wrapping_add(EMP_R4_A[j]),ls.wrapping_add(EMP_R4_S[j]));q[j]=st as u8}'
new_loop='for j in 0..4{let(oa,os)=emp_r4_step(l.source,j);st=upd(st,la.wrapping_add(oa),ls.wrapping_add(os));q[j]=st as u8}'
p=rep(p,old_loop,new_loop,'route4 evaluator loops',2)

# Add POST identity for arbitrary lane ids and a direct empirical-id evaluator.
marker='pub fn empirical_lane_for_pre_post(pp:u8,pr:u8,op:u8,orot:u8)->Option<u8>{'
need(p,marker,'v713 pre/post helper')
p=p.replace(marker,'''pub fn prediction_post(id:u8)->Option<(u8,u8)>{
 if let Some(l)=emp_lane(id){return Some((l.post_proto,l.post_rot))}
 if id>=1&&id<=LANE_COUNT as u8{let l=lane(id);return Some((l.post_proto,l.post_rot))}
 None
}
'''+marker,1)

id_eval=r'''
pub fn evaluate_empirical_id(id:u8,state:u16,div:u16,ai:u32,si:u32)->Option<Prediction>{
 if !empirical_window_safe(ai,si){return None}let l=emp_lane(id)?;if !empirical_trusted_source(l.source){return None}let av=(div>>8)as u8;let sv=div as u8;
 let pre=apply_sums(state,l.full_a[av as usize],l.full_s[sv as usize]);let la=av.wrapping_add(l.last_a);let ls=sv.wrapping_add(l.last_s);let(mut support,mut mask,mut raw)=(0u8,0u8,0u16);
 if l.route==3{for i in 0..5usize{let mut st=pre;let mut q=[0u8;3];for j in 0..3{st=upd(st,la.wrapping_add(DEEP_A[i][j]),ls.wrapping_add(DEEP_S[i][j]));q[j]=st as u8}if q[0]>=0xc0{continue}let v=((q[1]as u16)<<8)|q[2]as u16;if shiny(v){support=support.saturating_add(DEEP_WEIGHT[i]);mask|=1<<i;if raw==0{raw=v}}}if support<MIN_SUPPORT_WEIGHT{return None}}
 else{let mut st=pre;let mut q=[0u8;4];for j in 0..4{let(oa,os)=emp_r4_step(l.source,j);st=upd(st,la.wrapping_add(oa),ls.wrapping_add(os));q[j]=st as u8}if q[0]<0xc0{return None}let v=((q[2]as u16)<<8)|q[3]as u16;if !shiny(v){return None}support=4;mask=1;raw=v}
 let s40=apply_sums(state,l.p40_a[av as usize],l.p40_s[sv as usize]);let d40=((av.wrapping_add(l.o40a)as u16)<<8)|sv.wrapping_add(l.o40s)as u16;
 let s716=apply_sums(state,l.p716_a[av as usize],l.p716_s[sv as usize]);let d716=((av.wrapping_add(l.o716a)as u16)<<8)|sv.wrapping_add(l.o716s)as u16;
 let d717=((av.wrapping_add(l.o717a)as u16)<<8)|sv.wrapping_add(l.o717s)as u16;let s717=upd(s716,(d717>>8)as u8,d717 as u8);
 Some(Prediction{lane_id:l.id,source:l.source,support_weight:support,shiny_mask:mask,raw,expected40_state:s40,expected40_div:d40,expected716_state:s716,expected716_div:d716,expected717_state:s717,expected717_div:d717})
}
'''
needle='\nfn edist(a:u32,b:u32)->u32{b.wrapping_sub(a)&0x3fff}\n'
need(p,needle,'empirical helper insertion point')
p=p.replace(needle,id_eval+needle,1)

# The rel40 empirical suffix evaluator must not use the known-bad source0097.
start=p.index('pub fn evaluate_empirical_post')
end=p.index('\nfn edist',start)
chunk=p[start:end]
chunk2=chunk.replace('let l=emp_lane(id)?;','let l=emp_lane(id)?;if !empirical_trusted_source(l.source){return None}',1)
if chunk2==chunk: raise SystemExit('v730 empirical_post trust patch failed')
p=p[:start]+chunk2+p[end:]
P.write_text(p)

# ---- Trace: actual-root GLOBAL BEAM ---------------------------------------
t=T.read_text()
# One bit records whether READY/TEST came from a PRE-matched model or a global
# speculative model. It never changes the UP+B execution path.
t=rep(t,'    practical_learn: u8,\n    practical_post_proto: u8,','    practical_learn: u8,\n    practical_global_speculative: bool,\n    practical_post_proto: u8,','global field')
t=rep(t,'            practical_learn: 0,\n            practical_post_proto: 0,','            practical_learn: 0,\n            practical_global_speculative: false,\n            practical_post_proto: 0,','global default')
t=rep(t,'        self.practical_learn = 0;\n        self.practical_post_proto = 0;','        self.practical_learn = 0;\n        self.practical_global_speculative = false;\n        self.practical_post_proto = 0;','global reset')

s=t.index('    fn practical_wait_monitor(&mut self,reader:&Gen2Reader){')
e=t.index('\n    fn practical_fail',s)
new_monitor=r'''    fn practical_wait_monitor(&mut self,reader:&Gen2Reader){
 if !self.practical_search_enabled||!self.practical_live_scan||self.probe_session||self.practical_active||self.practical_candidate_valid{return}let cur=rng_advance();if cur==self.practical_live_last_advance{return}self.practical_live_last_advance=cur;self.practical_live_checked=self.practical_live_checked.saturating_add(1);
 let cell=self.live_pre_cell();let mut matched_proven=None;let mut matched_emp=false;if let Some((proto,rot))=cell{matched_proven=practical::lane_for_pre(proto,rot);matched_emp=practical::empirical_has_pre(proto,rot);if matched_proven.is_some(){self.practical_live_lane_frames=self.practical_live_lane_frames.saturating_add(1)}if matched_emp{self.practical_empirical_cell_frames=self.practical_empirical_cell_frames.saturating_add(1)}}
 let Some(ai0)=add_div_tracker().index()else{self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);return};let Some(si0)=sub_div_tracker().index()else{self.practical_live_index_wait=self.practical_live_index_wait.saturating_add(1);return};let ai=(ai0 as u32)&0x3fff;let si=(si0 as u32)&0x3fff;let state=reader.rng_state();let div=measured_div();
 // Tier 1: PRE-matched branches. Preserve the strongest existing evidence first.
 if let Some(id)=matched_proven{self.practical_live_exact_eval=self.practical_live_exact_eval.saturating_add(1);if let Some(x)=practical::evaluate_exact(id,state,div,ai,si){self.practical_live_found_advance=cur;self.practical_live_found_state=state;self.practical_live_found_div=div;self.practical_live_found_lane=id;self.practical_live_found_tick=pnp::system_tick();self.practical_live_found_ai=ai;self.practical_live_found_si=si;self.practical_live_scan=false;self.practical_search_enabled=false;self.clear_transport_diag();self.practical_global_speculative=false;self.bind_practical_prediction(x);self.practical_empirical=false;pnp::request_pause();return}}
 if let Some((proto,rot))=cell{if matched_emp{if !practical::empirical_window_safe(ai,si){self.practical_empirical_skip_exception=self.practical_empirical_skip_exception.saturating_add(1)}else{self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);if let Some(x)=practical::evaluate_empirical(proto,rot,state,div,ai,si){self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);self.practical_live_found_advance=cur;self.practical_live_found_state=state;self.practical_live_found_div=div;self.practical_live_found_lane=x.lane_id;self.practical_live_found_tick=pnp::system_tick();self.practical_live_found_ai=ai;self.practical_live_found_si=si;self.practical_live_scan=false;self.practical_search_enabled=false;self.clear_transport_diag();self.practical_global_speculative=false;self.bind_practical_prediction(x);self.practical_empirical=true;pnp::request_pause();return}}}}
 // Tier 2: global speculative branches. We no longer multiply shiny rarity by
 // sparse PRE coverage. Any hit is only TEST; rel40 must re-root to the actual
 // POST and prove a shiny suffix before the run is allowed to continue.
 for id in 1..=practical::proven_lane_count(){if Some(id)==matched_proven{continue}self.practical_live_exact_eval=self.practical_live_exact_eval.saturating_add(1);if let Some(x)=practical::evaluate_exact(id,state,div,ai,si){self.practical_live_found_advance=cur;self.practical_live_found_state=state;self.practical_live_found_div=div;self.practical_live_found_lane=id;self.practical_live_found_tick=pnp::system_tick();self.practical_live_found_ai=ai;self.practical_live_found_si=si;self.practical_live_scan=false;self.practical_search_enabled=false;self.clear_transport_diag();self.practical_global_speculative=true;self.bind_practical_prediction(x);self.practical_empirical=false;pnp::request_pause();return}}
 let first=practical::empirical_first_id();for k in 0..practical::empirical_count_u8(){let id=first.wrapping_add(k);self.practical_empirical_eval=self.practical_empirical_eval.saturating_add(1);if let Some(x)=practical::evaluate_empirical_id(id,state,div,ai,si){self.practical_empirical_candidates=self.practical_empirical_candidates.saturating_add(1);self.practical_live_found_advance=cur;self.practical_live_found_state=state;self.practical_live_found_div=div;self.practical_live_found_lane=x.lane_id;self.practical_live_found_tick=pnp::system_tick();self.practical_live_found_ai=ai;self.practical_live_found_si=si;self.practical_live_scan=false;self.practical_search_enabled=false;self.clear_transport_diag();self.practical_global_speculative=true;self.bind_practical_prediction(x);self.practical_empirical=true;pnp::request_pause();return}}
 }
'''
t=t[:s]+new_monitor+t[e:]

# rel40: POST identity may have multiple donors (A/r2 already does). Evaluate
# every donor from the ACTUAL rel40 root and accept only one shiny continuation.
s=t.index('    fn rebind_known_post_v720')
e=t.index('    fn enter_stage3_learn',s)
resolver=r'''    fn rebind_shiny_post_v730(&mut self,post_proto:u8,post_rot:u8,state40:u16,div40:u16)->bool{
        let (Some(ai0),Some(si0))=(add_div_tracker().index(),sub_div_tracker().index())else{return false};let ai=(ai0 as u32)&0x3fff;let si=(si0 as u32)&0x3fff;
        let mut count=0u8;let mut hit=None;let mut hit_emp=false;
        for id in 1..=practical::proven_lane_count(){if practical::prediction_post(id)!=Some((post_proto,post_rot)){continue}if let Some(x)=practical::evaluate_post_exact(id,state40,div40,ai,si){count=count.saturating_add(1);if count==1{hit=Some(x);hit_emp=false}}}
        let first=practical::empirical_first_id();for k in 0..practical::empirical_count_u8(){let id=first.wrapping_add(k);if practical::prediction_post(id)!=Some((post_proto,post_rot)){continue}if let Some(x)=practical::evaluate_empirical_post(id,state40,div40,ai,si){count=count.saturating_add(1);if count==1{hit=Some(x);hit_emp=true}}}
        if count!=1{return false}if let Some(x)=hit{self.practical_empirical=hit_emp;self.practical_global_speculative=false;self.rebind_practical_post_v690(x,post_proto,post_rot);return true}false
    }

'''
t=t[:s]+resolver+t[e:]
t=t.replace('rebind_known_post_v720(','rebind_shiny_post_v730(')

# UI/telemetry. UP+B wording is intentionally preserved; only the epoch changes.
t=t.replace('"S720 ','"S730 ')
scan='''                pnp::println!(
                    "EV{} SK{}",
                    self.practical_live_exact_eval.saturating_add(self.practical_empirical_eval),
                    self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception)
                );'''
need(t,scan,'v712 scan counters')
scan2=scan+'''
                if let Some((fp,fr))=self.live_pre_cell(){let name=match fp{b'A'=>"A",b'B'=>"B",b'C'=>"C",b'D'=>"D",_=>"?"};pnp::println!("FP {}{} N{}",name,fr,practical::known_pre_rot_count(fp));}else{pnp::println!("FP -- N0");}'''
t=t.replace(scan,scan2,1)
tele='            let _=write!(line,"STAGE3,V710,'
need(t,tele,'stage3 telemetry')
t=t.replace(tele,'            let _=write!(line,"GLOBALBEAM,V730,{}\\n",self.practical_global_speculative as u8);pnp::trace_file_write(line.as_bytes());line.clear();\n'+tele,1)

for m in ['S730 SCAN','S730 TEST UP+B','fn rebind_shiny_post_v730','GLOBALBEAM,V730','practical_expected716_state','practical_expected717_state']:
    need(t,m,'post-patch '+m)
if 'S720 ' in t: raise SystemExit('v730 stale S720 UI')
T.write_text(t)
print('Applied Suicune v7.3 GlobalBeam: UP+B preserved; 0102-0104 bank added; source0097 prediction quarantined; global actual-root scan; rel40 shiny-only unique rebind')
