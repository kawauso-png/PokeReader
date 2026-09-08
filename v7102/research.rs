//! Causal-data collector. Instrumented runs are NEVER production predictions.
//! Buffers are static; no formatting, allocation, SD access or pause in samples.
use crate::pnp;
use super::{game_lib::gb_mem,hook};
use alloc::string::String;
use core::fmt::Write;
#[path="capture_plan.rs"] mod plan;
extern "C" { fn host_suicune_research_mode()->u32; }
const CPU:u32=0x0022f5e0;
const DIV_PTR:u32=0x0022f794;
const SUB:u32=0x0022f604;
const DIV_REMAIN:u32=0x0022fa50;
const WRAM_PTR:u32=0x0022f6c8;
const HRAM_PTR:u32=0x0022f6d8;
const RAM_LEN:usize=8192;
// Immutable native code around the observed emulator PC 0014AAA4 and LR
// 001AF120. Read only while frozen; never copy this in an active hook.
const NATIVE_BASE:u32=0x00100000;
const NATIVE_LEN:usize=0x000b1000;
const EMU_LEN:usize=0x480; // 0022F5E0..0022FA5F, includes DIV countdown FA50.
static mut NATIVE_CODE:[u8;NATIVE_LEN]=[0;NATIVE_LEN];
static mut PRE_EMU:[u8;EMU_LEN]=[0;EMU_LEN];
static mut NATIVE_OK:bool=false;
static mut EMU_OK:bool=false;
unsafe fn range_mapped(base:u32,len:usize)->bool {
    if len==0 {return false;}
    let last=match base.checked_add((len-1) as u32) {Some(a)=>a,None=>return false};
    if !pnp::is_memory_mapped(base) || !pnp::is_memory_mapped(last) {return false;}
    let mut page=(base&!0xfff).saturating_add(0x1000);
    while page<=last {if !pnp::is_memory_mapped(page) {return false;} page+=0x1000;}
    true
}
unsafe fn capture_native_frozen() {
    NATIVE_OK=range_mapped(NATIVE_BASE,NATIVE_LEN);
    EMU_OK=range_mapped(CPU,EMU_LEN);
    if NATIVE_OK {copy(NATIVE_BASE,core::ptr::addr_of_mut!(NATIVE_CODE).cast::<u8>(),NATIVE_LEN);}
    if EMU_OK {copy(CPU,core::ptr::addr_of_mut!(PRE_EMU).cast::<u8>(),EMU_LEN);}
}
const HRAM_LEN:usize=127; // FF80..FFFE: excludes IE hardware register.

#[derive(Clone,Copy)]
struct Sample {
    frame:u32,advance:u32,rel:u32,pc:u16,div0:u8,sub0:u8,div1:u8,sub1:u8,
    tick0:u64,tick1:u64,remaining0:i32,remaining1:i32,
    ctx:[u8;64],audio:[u8;448],hram:[u8;HRAM_LEN],regs:[u32;15],stack:[u32;8],gb_stack:[u8;256],
}
impl Sample { const EMPTY:Self=Self {
    frame:0,advance:0,rel:0,pc:0,div0:0,sub0:0,div1:0,sub1:0,tick0:0,tick1:0,remaining0:0,remaining1:0,
    ctx:[0;64],audio:[0;448],hram:[0;HRAM_LEN],regs:[0;15],stack:[0;8],gb_stack:[0;256],
}; }
static mut FRAMES:[Sample;plan::FRAME_CAP]=[Sample::EMPTY;plan::FRAME_CAP];
static mut DEEP:[Sample;plan::DEEP_CAP]=[Sample::EMPTY;plan::DEEP_CAP];
static mut LCD:[Sample;32]=[Sample::EMPTY;32];
static mut NL:usize=0;
static mut DROP_L:u32=0;
static mut NF:usize=0;
static mut ND:usize=0;
static mut DROP_F:u32=0;
static mut DROP_D:u32=0;
static mut MODE:u32=0;
static mut TARGET:u32=0;
static mut ROOT_ADV:u32=0;
static mut ROOT_STATE:u16=0;
static mut PRE_AP:u16=0;
static mut PRE_SP:u16=0;
static mut ACTIVE:bool=false;
static mut PRE_OK:bool=false;
static mut MAP_OK:bool=false;
static mut AUDIO_HOST:u32=0;
static mut HRAM_HOST:u32=0;
static mut DIV_HOST:u32=0;
static mut PRE_RAM:[u8;RAM_LEN]=[0;RAM_LEN];
static mut PRE_HRAM:[u8;HRAM_LEN]=[0;HRAM_LEN];
static mut PRE_CPU:[u8;64]=[0;64];
static mut END_RAM:[u8;RAM_LEN]=[0;RAM_LEN];
static mut END_HRAM:[u8;HRAM_LEN]=[0;HRAM_LEN];
static mut END_CPU:[u8;64]=[0;64];
static mut END_ADV:u32=0;
static mut END_VALID:bool=false;

#[cfg(not(test))]
#[inline] unsafe fn byte(addr:u32)->u8 {core::ptr::read_volatile(addr as *const u8)}
#[cfg(test)]
#[inline] unsafe fn byte(addr:u32)->u8 {crate::pnp::test_byte(addr)}
#[cfg(not(test))]
#[inline] unsafe fn word(addr:u32)->u32 {core::ptr::read_volatile(addr as *const u32)}
#[cfg(test)]
#[inline] unsafe fn word(addr:u32)->u32 {u32::from_le_bytes([byte(addr),byte(addr+1),byte(addr+2),byte(addr+3)])}
unsafe fn copy(addr:u32,dst:*mut u8,len:usize) {pnp::read_into_raw(addr,dst,len);}
pub fn mode()->u32 { unsafe {MODE} }
pub fn mode_name()->&'static str { match mode() {1=>"TAIL",2=>"DEEP",_=>"BASE"} }
#[no_mangle] pub extern "C" fn suicune_research_arm_ok()->u32 {unsafe {PRE_OK as u32}}

fn capture_pre(target:u32) {
    unsafe {
        ACTIVE=false;PRE_OK=false;MAP_OK=false;END_VALID=false;
        capture_native_frozen();
        MODE=host_suicune_research_mode().min(2);TARGET=target;NF=0;ND=0;NL=0;DROP_L=0;DROP_F=0;DROP_D=0;
        // Frozen RAM-only reads. No ROM/save/IO accesses and no guest execution.
        for i in 0..RAM_LEN { PRE_RAM[i]=gb_mem::read_u8(0xc000+i as u32); }
        for i in 0..HRAM_LEN { PRE_HRAM[i]=gb_mem::read_u8(0xff80+i as u32); }
        if !pnp::is_memory_mapped(CPU) || !pnp::is_memory_mapped(CPU+63) {return;}
        copy(CPU,core::ptr::addr_of_mut!(PRE_CPU).cast::<u8>(),64);
        let wram=word(WRAM_PTR);
        let hram=word(HRAM_PTR);
        let audio=match wram.checked_add(0x100) {Some(p)=>p,None=>return};
        if audio.checked_add(447).is_none() || hram.checked_add(126).is_none() {return;}
        if !pnp::is_memory_mapped(wram) || !pnp::is_memory_mapped(audio) || !pnp::is_memory_mapped(audio+447)
            || !pnp::is_memory_mapped(hram) || !pnp::is_memory_mapped(hram+126) {return;}
        // Validate host aliases against the GB dispatcher's frozen RAM view.
        for i in 0..448 {if byte(audio+i as u32)!=PRE_RAM[0x100+i] {return;}}
        for i in 0..256 {if byte(wram+i as u32)!=PRE_RAM[i] {return;}}
        for i in 0..HRAM_LEN {if byte(hram+i as u32)!=PRE_HRAM[i] {return;}}
        let div=word(DIV_PTR);
        if div==0 || !pnp::is_memory_mapped(div) || !range_mapped(DIV_REMAIN,4) {return;}
        DIV_HOST=div;
        AUDIO_HOST=audio;HRAM_HOST=hram;MAP_OK=true;
        let st=((PRE_HRAM[0x61] as u16)<<8)|PRE_HRAM[0x62] as u16;
        PRE_OK=hook::rng_advance()==target && gb_mem::read_u16(0xffe1)==st;
        ACTIVE=PRE_OK;
    }
}

pub fn arm(target:u32,root_advance:u32,root_state:u16) {
    unsafe {ROOT_ADV=root_advance;ROOT_STATE=root_state;}
    capture_pre(target);
    unsafe {
        let total=(root_state>>8) as u32+450;
        let sub=(root_state as u8).wrapping_sub(451u16 as u8).wrapping_sub((total>>8) as u8);
        let expected=(((total&255) as u16)<<8)|sub as u16;
        let actual=((PRE_HRAM[0x61] as u16)<<8)|PRE_HRAM[0x62] as u16;
        let ap=((hook::measured_div()>>8)<<6)|(hook::adiv_subtick() as u16);
        let sp=((hook::measured_div()&255)<<6)|(hook::sdiv_subtick() as u16);
        PRE_AP=ap;PRE_SP=sp;
        PRE_OK=PRE_OK && target.wrapping_sub(root_advance)==3 && actual==expected && ap==0x2a35 && sp==0x2a40;
        ACTIVE=PRE_OK;
        // Persist an unusable capture too, so a failed setup is diagnosable.
        // This is SD telemetry while frozen; no guest memory is written.
        if !PRE_OK && pnp::trace_file_open(0) {
            save();pnp::trace_file_close();
        }
    }
}

// Caller is single-threaded and paused inside an existing callback. No bulk
// temporary Sample is created on the small ARM hook stack.
unsafe fn sample(dst:*mut Sample,frame:u32,advance:u32,pc:u16,regs:Option<(&[u32],*mut u32)>) {
    let s=&mut *dst;
    s.tick0=pnp::system_tick();s.div0=byte(DIV_HOST);s.sub0=byte(SUB);s.remaining0=word(DIV_REMAIN) as i32;
    s.frame=frame;s.advance=advance;s.rel=advance.wrapping_sub(TARGET).wrapping_sub(1);s.pc=pc;
    copy(CPU,s.ctx.as_mut_ptr(),64);
    copy(AUDIO_HOST,s.audio.as_mut_ptr(),448);
    // ROM 01B9 initializes SP=C0FF. Retain C000..C0FF so guest return
    // addresses can be decoded independently of the host ARM stack.
    copy(AUDIO_HOST-0x100,s.gb_stack.as_mut_ptr(),256);
    copy(HRAM_HOST,s.hram.as_mut_ptr(),HRAM_LEN);
    if let Some((r,stack))=regs {
        for i in 0..15 {s.regs[i]=r.get(i).copied().unwrap_or(0);}
        for i in 0..8 {s.stack[i]=core::ptr::read_volatile(stack.add(i));}
    }
    s.div1=byte(DIV_HOST);s.sub1=byte(SUB);s.remaining1=word(DIV_REMAIN) as i32;s.tick1=pnp::system_tick();
}

pub fn frame(frame:u32,advance:u32) {
    unsafe {
        if !ACTIVE || MODE!=1 || !MAP_OK {return;}
        let rel=advance.wrapping_sub(TARGET).wrapping_sub(1);
        if !plan::wants_frame(rel) {return;}
        if NF>=plan::FRAME_CAP {DROP_F=DROP_F.saturating_add(1);return;}
        let pc=(byte(CPU+0x1c) as u16)|((byte(CPU+0x1d) as u16)<<8);
        sample(core::ptr::addr_of_mut!(FRAMES).cast::<Sample>().add(NF),frame,advance,pc,None);
        NF+=1;
    }
}

pub fn div_boundary(advance:u32,pc:u16,regs:&[u32],stack:*mut u32) {
    unsafe {
        if !ACTIVE || MODE!=2 || !MAP_OK || !plan::is_div_pc(pc) {return;}
        if ND>=plan::DEEP_CAP {DROP_D=DROP_D.saturating_add(1);return;}
        sample(core::ptr::addr_of_mut!(DEEP).cast::<Sample>().add(ND),u32::MAX,advance,pc,Some((regs,stack)));
        ND+=1;
    }
}

// Crystal JP LCD ISR: PUSH AF at 0552, LDH A,[FFC6] at 0553.
// The GB read hook sees the operand PC 0554. Observe it without injecting IRQs.
pub fn lcd_boundary(advance:u32,pc:u16,regs:&[u32],stack:*mut u32) {
    unsafe {
        if !ACTIVE || MODE!=2 || !MAP_OK || pc!=0x0554 {return;}
        if NL>=32 {DROP_L=DROP_L.saturating_add(1);return;}
        sample(core::ptr::addr_of_mut!(LCD).cast::<Sample>().add(NL),u32::MAX,advance,pc,Some((regs,stack)));
        NL+=1;
    }
}
pub fn finish() {
    unsafe {
        if !ACTIVE {return;}
        ACTIVE=false;END_ADV=hook::rng_advance();
        for i in 0..RAM_LEN {END_RAM[i]=gb_mem::read_u8(0xc000+i as u32);}
        for i in 0..HRAM_LEN {END_HRAM[i]=gb_mem::read_u8(0xff80+i as u32);}
        copy(CPU,core::ptr::addr_of_mut!(END_CPU).cast::<u8>(),64);
        END_VALID=hook::rng_advance()==END_ADV;
    }
}
fn hex(line:&mut String,bytes:&[u8]) {for b in bytes {let _=write!(line,"{:02X}",b);}}
fn blob(tag:&str,base:u32,bytes:&[u8],line:&mut String) {
    let chunk_len=if tag=="NATIVE_CODE" {512} else {64};
    for (i,chunk) in bytes.chunks(chunk_len).enumerate() {
        line.clear();let _=write!(line,"R7102_BLOB,{},{:08X},{},",tag,base,i*chunk_len);
        hex(line,chunk);line.push('\n');pnp::trace_file_write(line.as_bytes());
    }
}
fn emit_sample(kind:&str,i:usize,s:&Sample,line:&mut String) {
    line.clear();
    let state=((s.hram[0x61] as u16)<<8)|s.hram[0x62] as u16;
    let _=write!(line,"R7102_SAMPLE,{},{},{},{},{},{:04X},{:04X},{:02X},{:02X},{:02X},{:02X},{},{},",
        kind,i,s.frame,s.advance,s.rel,s.pc,state,s.div0,s.sub0,s.div1,s.sub1,s.tick0,s.tick1);
    hex(line,&s.ctx);line.push(',');hex(line,&s.audio);line.push(',');hex(line,&s.hram);line.push(',');
    for r in s.regs {let _=write!(line,"{:08X}",r);}line.push(',');
    for r in s.stack {let _=write!(line,"{:08X}",r);}line.push(',');
    hex(line,&s.gb_stack);let _=write!(line,",{},{}\n",s.remaining0,s.remaining1);
    pnp::trace_file_write(line.as_bytes());
}
pub fn save() {
    let mut line=String::new();
    unsafe {
        let _=write!(line,"\nresearch7102,mode,target,pre_ok,map_ok,frames,deep,dropped_frames,dropped_deep,end_advance,end_valid,root_advance,root_state,pre_ap,pre_sp,audio_host,hram_host,div_source,div_host,native_ok,emu_ok,native_base,native_len,emu_len,lcd_samples,dropped_lcd\nR7102_META,{},{},{},{},{},{},{},{},{},{},{},{:04X},{:04X},{:04X},{:08X},{:08X},indirect,{:08X},{},{},{:08X},{},{},{},{}\n",
            mode_name(),TARGET,PRE_OK as u8,MAP_OK as u8,NF,ND,DROP_F,DROP_D,END_ADV,END_VALID as u8,ROOT_ADV,ROOT_STATE,PRE_AP,PRE_SP,AUDIO_HOST,HRAM_HOST,DIV_HOST,NATIVE_OK as u8,EMU_OK as u8,NATIVE_BASE,NATIVE_LEN,EMU_LEN,NL,DROP_L);
        pnp::trace_file_write(line.as_bytes());
        if NATIVE_OK {blob("NATIVE_CODE",NATIVE_BASE,&*core::ptr::addr_of!(NATIVE_CODE),&mut line);}
        if EMU_OK {blob("PRE_EMU",CPU,&*core::ptr::addr_of!(PRE_EMU),&mut line);}
        blob("PRE_RAM",0xc000,&*core::ptr::addr_of!(PRE_RAM),&mut line);blob("PRE_HRAM",0xff80,&*core::ptr::addr_of!(PRE_HRAM),&mut line);blob("PRE_CPU",CPU,&*core::ptr::addr_of!(PRE_CPU),&mut line);
        blob("END_RAM",0xc000,&*core::ptr::addr_of!(END_RAM),&mut line);blob("END_HRAM",0xff80,&*core::ptr::addr_of!(END_HRAM),&mut line);blob("END_CPU",CPU,&*core::ptr::addr_of!(END_CPU),&mut line);
        pnp::trace_file_write(b"research_sample,kind,index,frame,advance,rel,pc,state,div_before,sub_before,div_after,sub_after,tick_begin,tick_end,cpu_hex,audio_hex,hram_hex,arm_regs_hex,host_stack_hex,gb_stack_c000_c0ff_hex,div_remaining_before,div_remaining_after\n");
        for i in 0..NF {emit_sample("FRAME",i,&FRAMES[i],&mut line);}
        for i in 0..ND {emit_sample("DIV",i,&DEEP[i],&mut line);}
        for i in 0..NL {emit_sample("LCD",i,&LCD[i],&mut line);}
    }
}
