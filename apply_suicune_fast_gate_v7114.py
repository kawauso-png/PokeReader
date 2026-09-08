"""Stamp the optimized candidate gate and remove obsolete status guidance."""
from pathlib import Path
r=Path(__file__).resolve().parent
p=r/'3gx/sources/main.c';s=p.read_text();assert 'S7113' in s
s=s.replace('S7113','S7114')
a='                        v7102_panel("S7114 PREDICTION STOPPED",info,"NO UP - RECORD ERROR CODE");'
assert s.count(a)==1
s=s.replace(a,'''                        if(gate7113_error()==0x711314) v7102_panel("S7114 CPU TOO SLOW","SPEED LIMIT EXCEEDED","LOG SAVED - NO UP SENT");
                        else v7102_panel("S7114 PREDICTION STOPPED",info,"NO UP - RECORD ERROR CODE");''');p.write_text(s)
p=r/'reader_core/src/crystal/trace.rs';s=p.read_text()
for version in ['S7111','S7112','S7113']:s=s.replace(version,'S7114')
s=s.replace('STALLPHASE,V7113,','STALLPHASE,V7114,').replace('S7114 CLOCK RECORD SEARCH','S7114 SHINY SEARCH')
a='            pnp::println!("B -> RELEASE; WAIT -> UP");';assert s.count(a)==1
s=s.replace(a,'            pnp::println!("WAIT FOR TRY SHINY DV");')
a='            pnp::println!("NEUTRAL {}F FIXED",sp.slot);';assert s.count(a)==1
s=s.replace(a,'            pnp::println!("ADV{} NEUTRAL{}F",rng_advance(),sp.slot);');p.write_text(s)
print('Applied v7114: faster unchanged native simulation, speed/CPU diagnostics, current status and input guidance')
