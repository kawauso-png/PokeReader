from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
p=r/'3gx/sources/v7113_gate_runtime.c';s=p.read_text();assert 'gate7119_poll' not in s
anchor='uint32_t gate7118_export(uint32_t *pid_out) {'
assert s.count(anchor)==1;s=s.replace(anchor,'static void mac7119_exported(const Snapshot7116Meta*,const uint32_t*);\n'+anchor)
anchor='if(!snapshot7118_save(&m,(const uint8_t*)0x100000,data,(const uint8_t*)(uintptr_t)rom,hashes,pid))return 8;'
assert s.count(anchor)==1;s=s.replace(anchor,anchor+'\n mac7119_exported(&m,hashes);')
s+='\n'+(r/'v7119_mac/runtime.inc').read_text();p.write_text(s)
shutil.copyfile(r/'v7119_mac/protocol.h',r/'3gx/includes/mac7119_protocol.h')
p=r/'3gx/sources/v7116_snapshot.c';s=p.read_text();assert 'w[30]=7118' in s;s=s.replace('w[30]=7118','w[30]=7119').replace('\\"software\\":7118','\\"software\\":7119')
a='int snapshot7118_save(';assert s.count(a)==1;s=s.replace(a,'static unsigned mac7119_before_destination;\nvoid snapshot7119_destination(unsigned before){mac7119_before_destination=before;}\n'+a)
s=s.replace('const char *manifest="/luma/plugins/pokereader/mac_state.json";','const char *manifest=mac7119_before_destination?"/luma/plugins/pokereader/mac_before.json":"/luma/plugins/pokereader/mac_state.json";')
s=s.replace('const char *payload="/luma/plugins/pokereader/mac_state.bin";','const char *payload=mac7119_before_destination?"/luma/plugins/pokereader/mac_before.bin":"/luma/plugins/pokereader/mac_state.bin";')
s=s.replace('\\"snapshot\\":\\"/luma/plugins/pokereader/mac_state.bin\\"','\\"snapshot\\":\\"%s\\"')
a='(unsigned long)hashes[2],(unsigned long)hashes[3]);';assert s.count(a)==1;s=s.replace(a,'(unsigned long)hashes[2],(unsigned long)hashes[3],payload);')
s+='\n'+(r/'v7119_mac/io.inc').read_text();p.write_text(s)
p=r/'3gx/sources/main.c';s=p.read_text();assert 'gate7119_poll' not in s
s=s.replace('extern uint32_t gate7118_export(uint32_t*);','extern uint32_t gate7118_export(uint32_t*);\nextern unsigned gate7119_enabled(void),gate7119_running(void),gate7119_enable(void),gate7119_poll(uint32_t);\nextern void gate7119_disable(void);')
a='void handle_freeze(bool isTopScreen)';assert s.count(a)==1
s=s.replace(a,'''void host7119_status(unsigned stage,unsigned done,unsigned detail){
 char info[32];
 if(stage==1){snprintf(info,sizeof(info),"FR %u / %u",done,detail);v7102_panel("S7119 MAC STEP RUNNING",info,"KEEP ALL BUTTONS RELEASED");}
 else if(stage==2){snprintf(info,sizeof(info),"COMPLETED %u FRAMES",done);v7102_panel("S7119 MAC STEP DONE",info,"STILL PAUSED - MAC CAN READ");}
 else {snprintf(info,sizeof(info),"ERR %u DONE %u",detail,done);v7102_panel("S7119 MAC STEP ERROR",info,"RELEASE KEYS - STILL PAUSED");}
}

'''+a)
a='        if(mac7118_export_pending){';assert s.count(a)==1
s=s.replace(a,'''        if(gate7119_enabled()){
            if(!gate7119_running() && (just_pressed & KEY_SELECT)){
                gate7119_disable();mac7118_export_pending=true;continue;
            }
            if(!gate7119_running() && (held & KEY_Y) && (just_pressed & KEY_DDOWN)){
                gate7119_disable();
            }else{
                if(gate7119_poll(held))break; // one genuine frame, still logically paused
                svcSleepThread(1000000);continue;
            }
        }
'''+a)
a='uint32_t pid=0,e=gate7118_export(&pid);char info[32];';assert s.count(a)==1;s=s.replace(a,a+'\n            if(!e)e=gate7119_enable();')
s=s.replace('    while (is_paused && !isTopScreen)', '    if(gate7119_enabled())is_paused=true; // Mac mode always returns to the pause boundary\n    while (is_paused && !isTopScreen)')
s=s.replace('S7118','S7119');p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text().replace('S7118','S7119').replace('STALLPHASE,V7118,','STALLPHASE,V7119,');p.write_text(s)
p=r/'3gx/PokeReader.plgInfo';s=p.read_text();assert 'Revision: 18' in s;p.write_text(s.replace('Revision: 18','Revision: 19'))
print('Applied S7119 bounded Mac neutral steps; before/after export; no encounter launch')
