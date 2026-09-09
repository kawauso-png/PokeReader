from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
p=r/'3gx/sources/v7113_gate_runtime.c';s=p.read_text()
decl='static void gate7123_begin(void);\nvoid gate7123_note(uint32_t,uint64_t,uint32_t,uint32_t);\nint gate7123_finish(uint32_t,uint64_t,uint32_t,uint32_t);\n'
s=s.replace('static uint32_t error,checks',decl+'static uint32_t error,checks',1)
s=s.replace('void gate7113_cancel(void){','void gate7113_cancel(void){gate7123_finish(15,svcGetSystemTick(),get_current_keys(),0);',1)
s=s.replace('if(!committed)return;char line[256];','if(!committed)return;gate7123_finish(20,svcGetSystemTick(),0,(present?0x10000U:0U)|(dv&65535U));char line[256];',1)
old='mac7119_enabled_flag=0;free(mac7119_samples);mac7119_samples=NULL;return 0;'
assert s.count(old)==1;s=s.replace(old,'gate7123_begin();'+old)
s=s.replace('\\"software\\":7122','\\"software\\":7123');s+='\n'+(r/'v7123_diagnostics/runtime.inc').read_text();p.write_text(s)
shutil.copy2(r/'v7123_diagnostics/events7123.h',r/'3gx/includes/events7123.h')
p=r/'3gx/sources/main.c';s=p.read_text();s=s.replace('static void v7102_panel(',decl.replace('static void gate7123_begin(void);\n','')+'static void v7102_panel(',1)
s=s.replace('gate7113_cancel();suicune_wait_up_after_b=false;', 'gate7123_finish((just_pressed & KEY_SELECT)?11:10,now,held,0);\n                    gate7113_cancel();suicune_wait_up_after_b=false;',1)
s=s.replace('v7102_panel("S7122 CANDIDATE CANCELLED","Y+DOWN: SEARCH AGAIN","STILL PAUSED");','v7102_panel((just_pressed & KEY_SELECT)?"S7123 CANCELLED BY SELECT":"S7123 START DEADLINE MISSED","MAC CAN READ ERROR LOG","STILL PAUSED");')
s=s.replace('seconds>5?"WAIT - SELECT TO CANCEL":"HOLD UP NOW UNTIL PAUSED"','"HOLD UP NOW UNTIL PAUSED"')
s=s.replace('v7102_panel("S7122 MAC PREDICTION ARMED","WAIT FOR COUNTDOWN","SELECT: CANCEL CANDIDATE");','v7102_panel("S7123 MAC PREDICTION ARMED","HOLD UP NOW UNTIL PAUSED","SELECT: CANCEL CANDIDATE");')
for text,call in [('v7102_panel("S7122 RELEASE TOO LATE"','gate7123_finish(13,now,held,0);'),('v7102_panel("S7122 KEYS AT RESUME"','gate7123_finish(14,svcGetSystemTick(),get_current_keys(),0);'),('v7102_panel("S7122 RTC CAPTURE FAILED"','gate7123_finish(12,svcGetSystemTick(),held,0);')]:
 assert s.count(text)==1;s=s.replace(text,call+'\n                        '+text)
s=s.replace('v7102_release_shown=true;','v7102_release_shown=true;gate7123_note(3,svcGetSystemTick(),held,0);',1)
s=s.replace('suicune_obs_up_release_tick = now;','gate7123_note(4,now,held,0);\n                suicune_obs_up_release_tick = now;',1)
s=s.replace('suicune_phase_actual_tick = svcGetSystemTick();','suicune_phase_actual_tick = svcGetSystemTick();\n                gate7123_note(5,suicune_phase_actual_tick,0,0);',1)
needle='// v7.6.7d unchanged: the meaningful verification'
assert s.count(needle)==1;s=s.replace(needle,'gate7123_note(2,svcGetSystemTick(),held,0);\n\n                '+needle)
s=s.replace('S7122','S7123');p.write_text(s)
p=r/'3gx/sources/v7116_snapshot.c';s=p.read_text().replace('w[30]=7122','w[30]=7123').replace('\\"software\\":7122','\\"software\\":7123');p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';p.write_text(p.read_text().replace('S7122','S7123').replace('STALLPHASE,V7122,','STALLPHASE,V7123,'))
p=r/'3gx/PokeReader.plgInfo';p.write_text(p.read_text().replace('Revision: 22','Revision: 23'))
print('Applied S7123: terminal event log and early physical-UP cue; timing and guest guards unchanged')
