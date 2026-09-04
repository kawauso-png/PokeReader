from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()

old = '''        let ai = (ai0 as u32) & 0x3fff;\n        let si = (si0 as u32) & 0x3fff;\n\n        self.phase_target_proto = b'A';\n'''
new = '''        let ai = (ai0 as u32) & 0x3fff;\n        let si = (si0 as u32) & 0x3fff;\n        // v7.6.7 W-eff repeatability probe: hold the strongest naturally\n        // reproducible recorded PRE context fixed.  Do not write or restore\n        // tracker state; simply ignore roots outside this exact index pair.\n        if ai != 10694 || si != 9981 { return; }\n\n        self.phase_target_proto = b'A';\n'''
if old not in t:
    raise SystemExit('v767 AI/SI filter anchor missing')
t = t.replace(old, new, 1)

t = t.replace('pnp::println!("S766 PHASE PROBE SCAN");', 'pnp::println!("S767 W-EFF PROBE SCAN");', 1)
t = t.replace('pnp::println!("Y+DOWN -> A/r10 B76");', 'pnp::println!("Y+DOWN A/r10 B76 IDX");', 1)
t = t.replace('pnp::println!("S766 REL40 CAPTURED");', 'pnp::println!("S767 REL40 CAPTURED");', 1)
old_ready = '''                pnp::println!("S766 A/r10 B76 LOCK");\n                pnp::println!("T{} S{:04X} D{:04X}",self.practical_target,self.practical_live_found_state,self.practical_live_found_div);\n                pnp::println!("RESUME M{:02} X+1 Y-1",pnp::fixed_a_frame().phase_slot & 15);\n                pnp::println!("B -> RELEASE -> UP");'''
new_ready = '''                pnp::println!("S767 A/r10 B76 IDX");\n                pnp::println!("T{} S{:04X} D{:04X}",self.practical_target,self.practical_live_found_state,self.practical_live_found_div);\n                pnp::println!("AI10694 SI9981 M14");\n                pnp::println!("B -> RELEASE -> UP");'''
if old_ready not in t:
    raise SystemExit('v767 ready UI anchor missing')
t = t.replace(old_ready, new_ready, 1)
t = t.replace('pnp::println!("S766 RESET RECOMMENDED");', 'pnp::println!("S767 RESET RECOMMENDED");', 1)

old_csv = '''        let _=write!(line,"\\nphase_utility,version,pre_proto,pre_rot,bucket,target_advance,state,div,post_proto,post_rot,state40,div40,gate_models,gate_eval,gate_shiny,miss\\nPHASEUTILITY,V766,{},{},{},{},{:04X},{:04X},{},{},{:04X},{:04X},{},{},{},{}\\n",\n            self.phase_target_proto as char,self.phase_target_rot,self.bucket_current,self.practical_target,\n            self.practical_live_found_state,self.practical_live_found_div,\n            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,\n            self.v763_rel40_state,self.v763_rel40_div,self.v763_gate_models,self.v763_gate_evaluated,self.v763_gate_shiny_models,self.practical_miss);\n'''
new_csv = '''        let _=write!(line,"\\nw_eff_probe,version,pre_proto,pre_rot,bucket,target_advance,state,div,ai,si,resume_m,post_proto,post_rot,state40,div40,gate_models,gate_eval,gate_shiny,miss\\nWPROBE,V767,{},{},{},{},{:04X},{:04X},{},{},14,{},{},{:04X},{:04X},{},{},{},{}\\n",\n            self.phase_target_proto as char,self.phase_target_rot,self.bucket_current,self.practical_target,\n            self.practical_live_found_state,self.practical_live_found_div,self.practical_live_found_ai,self.practical_live_found_si,\n            if self.practical_post_proto==0{'?'}else{self.practical_post_proto as char},self.practical_post_rot,\n            self.v763_rel40_state,self.v763_rel40_div,self.v763_gate_models,self.v763_gate_evaluated,self.v763_gate_shiny_models,self.practical_miss);\n'''
if old_csv not in t:
    raise SystemExit('v767 csv marker anchor missing')
t = t.replace(old_csv, new_csv, 1)
T.write_text(t)

C = Path('3gx/sources/main.c')
c = C.read_text()
old_scan = '''                suicune_phase_slot = 0; // v7.6.6 diagnostic default: absolute Resume M0\n                search_suicune_practical_targets();'''
new_scan = '''                suicune_phase_slot = 14; // v7.6.7 W-eff probe: Resume M14 fixed\n                search_suicune_practical_targets();'''
if old_scan not in c:
    raise SystemExit('v767 scan M anchor missing')
c = c.replace(old_scan, new_scan, 1)

old_control = '''        // v7.4.2 full absolute resume selector.  Only active after the\n        // authoritative frozen A/r10 bucket root is READY, so Y+DOWN/Y+UP\n        // scan commands cannot collide with this control.  X=+1, Y=-1.\n        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            if (just_pressed & KEY_X)\n            {\n                suicune_phase_slot = (suicune_phase_slot + 1U) & 15U;\n                continue;\n            }\n            if (just_pressed & KEY_Y)\n            {\n                suicune_phase_slot = (suicune_phase_slot + 15U) & 15U;\n                continue;\n            }\n        }\n'''
new_control = '''        // v7.6.7 repeatability probe: Resume M is intentionally immutable.\n        // X/Y must not change the landing condition after a qualifying root locks.\n        if (suicune_root_lock_ready && !fixed_run_pending && !suicune_auto_resume_pending)\n        {\n            suicune_phase_slot = 14U;\n        }\n'''
if old_control not in c:
    raise SystemExit('v767 M selector disable anchor missing')
c = c.replace(old_control, new_control, 1)

# Also reassert M14 at the B arm point so an old slot can never leak into a run.
old_arm = '''            suicune_wait_up_after_b = true;\n            suicune_phase_lock_active = true;\n            suicune_phase_anchor_tick = 0;'''
new_arm = '''            suicune_wait_up_after_b = true;\n            suicune_phase_slot = 14U;\n            suicune_phase_lock_active = true;\n            suicune_phase_anchor_tick = 0;'''
if old_arm not in c:
    raise SystemExit('v767 arm M14 anchor missing')
c = c.replace(old_arm, new_arm, 1)
C.write_text(c)

print('Applied v7.6.7 W-eff probe: A/r10 B76 + AI10694/SI9981, Resume M14 fixed, rel40 stop')
