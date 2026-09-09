from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
p=r/'3gx/sources/main.c';s=p.read_text();assert 'manual7121_active' not in s
a='int host7120_arm(void){';assert s.count(a)==1
s=s.replace(a,(r/'v7121_manual/integration.inc').read_text()+a)
s=s.replace(a,a+'\n manual7121_active=false;manual7121_control.pending=0;')
a='        if(gate7119_enabled()){';assert s.count(a)==1
s=s.replace(a,'''        /* Enter manual control only before a physical encounter has started. */
        if(is_gen_2 && !gate7119_running() && !fixed_run_pending && !fixed_frames_remaining
            && !suicune_auto_resume_pending && !suicune_exact2_release_waiting()
            && held==(KEY_Y|KEY_SELECT) && (just_pressed&KEY_SELECT)){
            manual7121_enter();continue;
        }
        if(gate7119_enabled() && !gate7119_running()
            && ((held==KEY_START && (just_pressed&KEY_START)) || (held==KEY_L && (just_pressed&KEY_L)))){
            manual7121_enter();
        }
        if(manual7121_active && !gate7119_enabled()){
            unsigned action=manual7121_poll(&manual7121_control,just_pressed,held);
            if(action==MANUAL_STEP){
                manual7121_released=true;
                break;
            }
            if(action==MANUAL_RUN){
                v7102_panel("S7121 NORMAL RUN","L+R: PAUSE","NO CANDIDATE ARMED");
                manual7121_released=true;is_paused=false;break;
            }
            if(action==MANUAL_EXPORT){
                manual7121_active=false;mac7118_export_pending=true;continue;
            }
            svcSleepThread(1000000);continue;
        }
'''+a)
# Tell users where they are when LR returns from ordinary free running.
a='        is_paused = true;\n    }\n\n    if(gate7119_enabled())';assert s.count(a)==1
s=s.replace(a,'        is_paused = true;\n        if(manual7121_active)manual7121_panel();\n    }\n\n    if(gate7119_enabled())')
# Count display boundaries in both normal run and L stepping, from the frozen origin.
a='    u64 masked_title_id = get_title_id() & 0xfff000;'
assert s.count(a)==1
s=s.replace(a,'''    if(!isTopScreen && manual7121_active && manual7121_released){
        manual7121_frames++;manual7121_released=false;
        if(is_paused)manual7121_panel();
    }
'''+a)
a='        svcSleepThread(50000000);\n    }\n}'
assert s.count(a)==1
s=s.replace(a,'        svcSleepThread(50000000);\n    }\n    if(!isTopScreen && manual7121_active && !is_paused)manual7121_released=true;\n}')
s=s.replace('S7120 MAC CANDIDATE ARMED','S7120 MAC PREDICTION ARMED').replace('TRY SHINY DV','PREDICTED DV').replace('S7120','S7121');p.write_text(s)
shutil.copyfile(r/'v7121_manual/manual.h',r/'3gx/includes/manual7121.h')
p=r/'3gx/sources/v7116_snapshot.c';s=p.read_text();assert 'w[30]=7120' in s
s=s.replace('w[30]=7120','w[30]=7121').replace('\\"software\\":7120','\\"software\\":7121');p.write_text(s)
p=r/'3gx/sources/v7113_gate_runtime.c';s=p.read_text();old=(r/'v7120_mac/runtime.inc').read_text();assert old in s
s=s.replace(old,(r/'v7121_manual/runtime.inc').read_text()).replace('return selected!=0;','return committed||selected!=0;').replace('return selected&&committed&&target==advance','return committed&&target==advance');p.write_text(s)
shutil.copyfile(r/'v7121_manual/protocol.h',r/'3gx/includes/mac7120_protocol.h')
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text().replace('S7120','S7121').replace('STALLPHASE,V7120,','STALLPHASE,V7121,');p.write_text(s)
p=r/'3gx/PokeReader.plgInfo';s=p.read_text();assert 'Revision: 20' in s;p.write_text(s.replace('Revision: 20','Revision: 21'))
print('Applied S7121 ordinary run, LR pause, released-key L step, fresh Mac export')
