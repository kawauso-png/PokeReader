"""Apply after v7108 ranked generation. Collection-only, first valid PRE."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
def rep(s,a,b):
    assert s.count(a)==1,(a[:90],s.count(a))
    return s.replace(a,b)
f=root/'reader_core/src/crystal/research.rs';s=f.read_text()
s=rep(s,'use crate::pnp;','''use crate::pnp;
#[path="clock7110.rs"] mod clock7110;
pub fn clock_observe(advance:u32,pc:u16,requested:u32){clock7110::observe(advance,pc,requested);}
''')
s=rep(s,'        ACTIVE=PRE_OK;\n        // Persist','''        clock7110::arm(target,IO_HOST,PRE_OK && IO_OK && EMU_OK && MODE==3);
        if MODE==3 && !clock7110::ready(){PRE_OK=false;}
        ACTIVE=PRE_OK;
        // Persist''')
s=rep(s,'pub fn finish() {','pub fn finish() {\n    clock7110::finish();')
s=rep(s,'pub fn frame(frame:u32,advance:u32) {','pub fn frame(frame:u32,advance:u32) {\n    clock7110::frame(frame);')
s=rep(s,'pub fn save() {','pub fn save() {\n    clock7110::save();')
f.write_text(s)
shutil.copy2(root/'v7110/clock.rs',root/'reader_core/src/crystal/clock7110.rs')
f=root/'reader_core/src/crystal/hook.rs';s=f.read_text()
s=rep(s,'    if requested == 0xffc6 &&','''    if requested==0xff04 || requested==0xffe9 || requested==0xffc6 {
        super::research::clock_observe(rng_advance(),Gen2Reader::crystal().pc_reg(),requested);
    }
    if requested == 0xffc6 &&''')
f.write_text(s)
f=root/'3gx/sources/main.c';s=f.read_text()
s=rep(s,'static bool rank7108_hunting=false;','static bool rank7108_hunting=false;\nstatic const bool clock7110_collection=true;')
s=rep(s,'                if(rank7108_hunting) {\n                    int decision=rank7108_evaluate();','                if(rank7108_hunting && !clock7110_collection) {\n                    int decision=rank7108_evaluate();')
s=rep(s,'if(suicune_live_pass_ready && rank7108_hunting) {','if(suicune_live_pass_ready && rank7108_hunting && !clock7110_collection) {')
s=s.replace('S7109','S7110')
s=s.replace('"S7110 RECORD ARMED"','"S7110 CLOCK RECORD READY"')
f.write_text(s)
f=root/'reader_core/src/crystal/trace.rs';s=f.read_text().replace('S7109','S7110').replace('STALLPHASE,V7109,','STALLPHASE,V7110,')
s=s.replace('S7110 RANK SEARCH','S7110 CLOCK RECORD SEARCH')
f.write_text(s)
print('Applied v7110: collect all normal/final DIV clocks and TIMER events at first valid PRE; no shiny selection')
