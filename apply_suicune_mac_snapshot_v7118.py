from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'3gx/sources/v7113_gate_runtime.c';s=p.read_text();assert 'gate7118_export' not in s;s+='\n'+(r/'v7118_mac/export.inc').read_text();p.write_text(s)
p=r/'3gx/sources/v7116_snapshot.c';s=p.read_text();assert 'w[30]=7117' in s;s=s.replace('w[30]=7117','w[30]=7118');s+='\n'+(r/'v7118_mac/save.inc').read_text();p.write_text(s)
p=r/'3gx/sources/main.c';s=p.read_text();a='static bool is_paused = false;';assert s.count(a)==1;s=s.replace(a,a+'\nstatic bool mac7118_export_pending=false;\nextern uint32_t gate7118_export(uint32_t*);')
a='            v7102_panel("S7117 SEARCH PAUSED","Y+DOWN: RESTART SEARCH","NO GAME INPUT SENT");';assert s.count(a)==1;s=s.replace(a,'            mac7118_export_pending=true;\n'+a)
a='        u32 held = get_current_keys();';assert s.count(a)==1;s=s.replace(a,a+'''
        if(mac7118_export_pending){
            if(held){svcSleepThread(1000000);continue;}
            mac7118_export_pending=false;
            v7102_panel("S7118 EXPORTING TO MAC","KEEP ALL BUTTONS RELEASED","STILL PAUSED");
            uint32_t pid=0,e=gate7118_export(&pid);char info[32];
            if(e){snprintf(info,sizeof(info),"ERROR %lu PID %lu",(unsigned long)e,(unsigned long)pid);v7102_panel("S7118 MAC EXPORT FAILED",info,"STILL PAUSED - NO INPUT");}
            else {snprintf(info,sizeof(info),"PID %lu - MAC CAN READ SD",(unsigned long)pid);v7102_panel("S7118 MAC SNAPSHOT READY",info,"STILL PAUSED - NO INPUT");}
            continue;
        }
''');s=s.replace('S7117','S7118');p.write_text(s)
p=r/'3gx/sources/main.c';s=p.read_text();a='                        if(gate7113_error()==0x711314) v7102_panel';assert s.count(a)==1;s=s.replace(a,'                        if(gate7113_error()==0x711301) mac7118_export_pending=true;\n'+a);p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text().replace('S7117','S7118').replace('STALLPHASE,V7117,','STALLPHASE,V7118,');p.write_text(s)
p=r/'3gx/PokeReader.plgInfo';s=p.read_text().replace('    Major: 1','    Major: 7').replace('    Minor: 0','    Minor: 10').replace('    Revision: 0','    Revision: 18');p.write_text(s)
print('Applied v7118 Mac snapshot: SELECT stops, release keys exports copy + PID; no auto launch')
