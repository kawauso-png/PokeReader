#!/usr/bin/env python3
from pathlib import Path
import base64
import json
import re
import zlib

P = Path("reader_core/src/crystal/practical.rs")
T = Path("reader_core/src/crystal/trace.rs")

DATA_B85 = 'c-o!VzjD(+5XbR%QN4wB?|({o3?>Bw6jWgXR1ELVD$(BllH6GrI(w{-R@T_-@A%L5^Wpd7mv7r0?}4`OUylcwwjV#XyY1tq4<5I>p^t1L6vke@pD9@QJiX7?YF#7BxrLK9MDO+5fXvgJhjp8b!nIY|@%1B%EoKk*xjKEaGBE<y`@s+M9#P5PCtT~lr~fRI3w%hV9d0TF_rQ2<4P-j5q}b_FaNPrPZf9RsmzSb?$!*yMUL4C4yS#3z7;f`y_CfZQ8<~P-JdEA7xA@dP@8cR>Gp~NQF^JfV&@Yc>5!GfZBp>J1x2pB!THow(8&jb1FOJ8kvi^Qg7U{5Y5Kx9B>4v%grwj#lr`Ae9|!$sT)jUI-+Gm6Yt1fK+8Yv<oC!XY6*S^T-y4ot1P!fP8)u3H^%u*x6J4Fu8}x9A-9Cl+Y%T`m&xKZ?K`<R)l?V9$_xjGL!TprS~G?IGvA5H~NPoqREw4x}c~M`Ab{x7C2v3FNm~5{P+!_rO7hN+1qU*I6?UCFfw$+`HIxyPj;qtG!g{=XxK6H^f^+Pt0d$$8}>qTn5~2-#0_4Lxl9B#S?KIr$}a6}9PA{e$2s0OW6Vx0c6wQ7@#fD^3?my1NGElhw=#4e{9Zf0BZ*Ab*53oBEA{!kc5?59AH~_!c?k)^=#M@#3l9~*yfeCe3GuGTvsYM<b(Uc9t@-h7VlyX`P3LmcrngmCgTD={a_9K``JzQ~E{1nU6VKCEeG@0O+N>f{Tve0)GyjXR0wtMb28L;ZHxb8fw~8oeIs-FKpo}3-YEK2{8BldR<|K8Xg+f0~Ptb8f0Q5jI}GCEwkUv5bOxM5pI*J`jyS!mz>vQe!s{?Qv_4)_+2eA^iV2zJm^bLy9rwiY|G%?Z7S6zYbTVM?T4z<Xwx8?_=PF2Gknh!0P+sQ6n1#3IA1^e6MBSE)TWvV-vCM>?nDXJV#7fFMw@K8H0mB$10O)fCkV=`B4+!1qJGI<hE0W6|V&JthRBG>Aq}T6$XJb$MwE1npd6Y)uC+Wg^BfnNJ({uRf>)@ah5X?{YV7Ck9LrmQ&AZiL2?C8vwZ5quv(Du6D-<JvQ9A7hA=3V(D6v<P{GN+8`W?bY>i8^H#K6i~Wnsm=mt!Udv?4`7>W%o8n5z(MF(M~Ptp91=uYH3A0XKja2pX{B+Yv9*l0m!Wl2m`j%v1vcw3=KmAkZj^YyTx`ax0Gu}CbpTG9aTb6J%{U9d>t^f$m|q6qdz*0(fVY}4b}|gWg=U-t;Jg{f0l3hNvjALZ##sO^G~?v|xc_X%<A?hG??1yK1hD'

def need(text, marker, label):
    if marker not in text:
        raise SystemExit(f"v721 missing {label}: {marker}")

def rep(text, old, new, label, expected=1):
    n = text.count(old)
    if n != expected:
        raise SystemExit(f"v721 {label}: expected {expected}, got {n}")
    return text.replace(old, new)

def upd(st, a, s):
    ra, rs = (st >> 8) & 0xff, st & 0xff
    z = ra + (a & 0xff)
    carry = 1 if z > 0xff else 0
    return ((z & 0xff) << 8) | ((rs - (s & 0xff) - carry) & 0xff)

def apply_sums(st, sa, ss):
    ra, rs = (st >> 8) & 0xff, st & 0xff
    total = ra + sa
    return ((total & 0xff) << 8) | ((rs - ss - (total // 256)) & 0xff)

def tab(raw, end):
    return [sum(((b + x) & 0xff) for x in raw[:end+1]) for b in range(256)]

def arr(name, vals):
    return "const " + name + ":[u32;256]=[" + ",".join(map(str, vals)) + "];\n"

def run_r4(st, base_a, base_s, oa, os):
    q = []
    for a, s in zip(oa, os):
        st = upd(st, (base_a + a) & 0xff, (base_s + s) & 0xff)
        q.append(st & 0xff)
    return st, q

d = json.loads(zlib.decompress(base64.b85decode(DATA_B85)).decode())
assert d["source"] == 103 and d["id"] == 106
assert d["pp"] == "C" and d["pr"] == 7
assert d["op"] == "B" and d["or"] == 6 and d["route"] == 4
a = d["a"]; s = d["s"]
if len(a) != 731 or len(s) != 731:
    raise SystemExit("v721 C/r7 payload must contain rel0..730")

# Evidence gates before touching source.
ba = bs = 0xC3
if apply_sums(0xE510, tab(a, 40)[ba], tab(s, 40)[bs]) != 0x8355:
    raise SystemExit("v721 0103 rel40 regression failed")
if apply_sums(0xE510, tab(a, 716)[ba], tab(s, 716)[bs]) != 0x55CF:
    raise SystemExit("v721 0103 rel716 regression failed")
if apply_sums(0xE510, tab(a, 717)[ba], tab(s, 717)[bs]) != 0x72B2:
    raise SystemExit("v721 0103 rel717 regression failed")
pre103 = apply_sums(0xE510, tab(a, 730)[ba], tab(s, 730)[bs])
if pre103 != 0xDC41:
    raise SystemExit(f"v721 0103 terminal VBlank root {pre103:04X} != DC41")
if ((ba + a[730]) & 0xff) != 0xC5 or ((bs + s[730]) & 0xff) != 0xC5:
    raise SystemExit("v721 0103 terminal DIV regression failed")

R4_OLD_A = [183,185,191,193]
R4_OLD_S = [183,186,191,193]
_, q101 = run_r4(0xADB8, 0x04, 0x04, R4_OLD_A, R4_OLD_S)
if q101[0] < 0xC0 or ((q101[2] << 8) | q101[3]) != 0x7AB4:
    raise SystemExit("v721 old route4 0101 regression failed")

# Independent old 0071 tail shape. This pattern is not fit from 0102/0103.
R4_ALT_A = [184,186,192,194]
R4_ALT_S = [184,186,192,194]
_, q102 = run_r4(0x7C64, 0xBC, 0xBC, R4_ALT_A, R4_ALT_S)
_, q103 = run_r4(0xDC41, 0xC5, 0xC5, R4_ALT_A, R4_ALT_S)
if q102[0] < 0xC0 or ((q102[2] << 8) | q102[3]) != 0xFD7E:
    raise SystemExit("v721 held-out 0102 route4 regression failed")
if q103[0] < 0xC0 or ((q103[2] << 8) | q103[3]) != 0xBE37:
    raise SystemExit("v721 held-out 0103 route4 regression failed")

p = P.read_text()
t = T.read_text()

for marker, label in [
    ("const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=5;", "v710 empirical bank"),
    ("const EMP_R4_A:[u8;4]=[183,185,191,193]; const EMP_R4_S:[u8;4]=[183,186,191,193];", "old route4 tail"),
    ("const EMP_LANES:[EmpLane;EMP_COUNT]=[", "empirical lane table"),
    ("pub fn empirical_has_pre", "target PRE coverage helper"),
    ("pub fn evaluate_empirical", "target empirical evaluator"),
    ("pub fn evaluate_empirical_post", "rel40 empirical evaluator"),
]:
    need(p, marker, label)
for marker, label in [
    ("S720 SCAN", "v720 scan UI"),
    ("S720 TEST UP+B", "v720 validation UI"),
]:
    need(t, marker, label)

defs = ""
for name, raw, end in [
    ("E6_FA", a, 730), ("E6_FS", s, 730),
    ("E6_A40", a, 40), ("E6_S40", s, 40),
    ("E6_A716", a, 716), ("E6_S716", s, 716),
]:
    defs += arr(name, tab(raw, end))

p = rep(
    p,
    "const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=5;",
    "const EMP_FIRST_ID:u8=101; const EMP_COUNT:usize=6;",
    "EMP_COUNT"
)
p = rep(
    p,
    "const EMP_R4_A:[u8;4]=[183,185,191,193]; const EMP_R4_S:[u8;4]=[183,186,191,193];",
    "const EMP_R4_A:[u8;4]=[183,185,191,193]; const EMP_R4_S:[u8;4]=[183,186,191,193];\n"
    "const EMP_R4_ALT_A:[u8;4]=[184,186,192,194]; const EMP_R4_ALT_S:[u8;4]=[184,186,192,194];\n"
    "#[inline] fn emp_r4_step(source:u16,j:usize)->(u8,u8){"
    "if source==103{(EMP_R4_ALT_A[j],EMP_R4_ALT_S[j])}else{(EMP_R4_A[j],EMP_R4_S[j])}}",
    "route4 per-lane selector"
)
p = rep(
    p,
    "const EMP_LANES:[EmpLane;EMP_COUNT]=[\n",
    defs + "const EMP_LANES:[EmpLane;EMP_COUNT]=[\n",
    "E6 table insertion"
)

lane = (
    "EmpLane{id:106,source:103,pre_proto:b'C',pre_rot:7,"
    "post_proto:b'B',post_rot:6,route:4,"
    "full_a:&E6_FA,full_s:&E6_FS,p40_a:&E6_A40,p40_s:&E6_S40,"
    "p716_a:&E6_A716,p716_s:&E6_S716,"
    f"o40a:{a[40]},o40s:{s[40]},o716a:{a[716]},o716s:{s[716]},"
    f"o717a:{a[717]},o717s:{s[717]},last_a:{a[730]},last_s:{s[730]}}},\n"
)
start = p.index("const EMP_LANES:[EmpLane;EMP_COUNT]=[")
end = p.index("];\nfn emp_lane", start)
p = p[:end] + lane + p[end:]

old_loop = "for j in 0..4{st=upd(st,la.wrapping_add(EMP_R4_A[j]),ls.wrapping_add(EMP_R4_S[j]));q[j]=st as u8}"
new_loop = "for j in 0..4{let(oa,os)=emp_r4_step(l.source,j);st=upd(st,la.wrapping_add(oa),ls.wrapping_add(os));q[j]=st as u8}"
if p.count(old_loop) != 2:
    raise SystemExit(f"v721 expected 2 route4 evaluator loops, got {p.count(old_loop)}")
p = p.replace(old_loop, new_loop)

if "empirical_lane_for_post_unique_global" not in p:
    raise SystemExit("v721 lost v720 global POST resolver")
P.write_text(p)

# Diagnostic overlay only; search rules are not loosened.
t = t.replace('"S720 ', '"S721 ')
scan_marker = '''                pnp::println!(
                    "EV{} SK{}",
                    self.practical_live_exact_eval.saturating_add(self.practical_empirical_eval),
                    self.practical_live_index_wait.saturating_add(self.practical_empirical_skip_exception)
                );'''
need(t, scan_marker, "v712 EV/SK scan row")
fp_block = scan_marker + '''
                if let Some((fp,fr))=self.live_pre_cell(){
                    let name=match fp{b'A'=>"A",b'B'=>"B",b'C'=>"C",b'D'=>"D",_=>"?"};
                    let known=practical::lane_for_pre(fp,fr).is_some()||practical::empirical_has_pre(fp,fr);
                    pnp::println!("FP {}{} K{}",name,fr,known as u8);
                }else{
                    pnp::println!("FP --");
                }'''
t = rep(t, scan_marker, fp_block, "FP diagnostic row")

for marker in ["S721 SCAN", "S721 TEST UP+B", "fn practical_wait_monitor", "POSTBEAM,V720"]:
    need(t, marker, "post-patch " + marker)
if "S720 " in t:
    raise SystemExit("v721 stale S720 UI remains")
T.write_text(t)

print("Applied v7.2.1 PRE-C coverage: C/r7 source0103 + per-lane route4 tail; 0101/0102/0103 regressions PASS")
