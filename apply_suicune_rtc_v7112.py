"""Apply after v7111. Record the missing RTC input before guest execution."""
from pathlib import Path
import shutil
r=Path(__file__).resolve().parent
f=r/'reader_core/src/crystal/research.rs';s=f.read_text()
def repl(a,b):
 global s
 assert s.count(a)==1,(a,s.count(a));s=s.replace(a,b)
repl('#[path="snapshot7111.rs"] mod snapshot7111;','#[path="snapshot7111.rs"] mod snapshot7111;\n#[path="rtc7112.rs"] mod rtc7112;')
repl('        ACTIVE=PRE_OK;\n        // Persist','        rtc7112::arm(target,PRE_OK && MODE==3);\n        ACTIVE=PRE_OK;\n        // Persist')
repl('    snapshot7111::save();','    rtc7112::save();\n    snapshot7111::save();')
f.write_text(s);shutil.copyfile(r/'v7112/rtc.rs',r/'reader_core/src/crystal/rtc7112.rs')
f=r/'3gx/sources/main.c';s=f.read_text()
repl('extern u32 suicune_research_arm_ok(void);','extern u32 suicune_research_arm_ok(void);\nextern u32 suicune_rtc7112_launch(void);')
repl('                // v7.6.7d unchanged: the meaningful verification is the', '''                // Capture launch RTC while still frozen, before physical UP runs.
                if (!suicune_rtc7112_launch()) {
                    v7102_panel("S7112 RTC CAPTURE FAILED","STILL PAUSED","RESET VC MANUALLY");
                    svcSleepThread(1000000);
                    continue;
                }

                // v7.6.7d unchanged: the meaningful verification is the''')
s=s.replace('S7111','S7112').replace('S7112 STATE RECORD READY','S7112 RTC RECORD READY');f.write_text(s)
f=r/'reader_core/src/crystal/trace.rs';f.write_text(f.read_text().replace('STALLPHASE,V7111,','STALLPHASE,V7112,'))
print('Applied v7112: frozen PRE/UP RTC references; guest CPU and Exact2/M14 unchanged')
