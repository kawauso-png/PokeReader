//! Compact clock observations at existing memory-read hooks. Guest read-only.
//! No allocation, formatting, SD access or pause inside observe().
use crate::pnp;
use alloc::string::String;
use core::fmt::Write;
const CAP:usize=4096;
#[derive(Clone,Copy)]
struct Clock {
    advance:u32,frame:u32,pc:u16,state:u16,kind:u8,
    div:u8,elapsed:u8,tima:u8,tma:u8,tac:u8,ie:u8,iflag:u8,
    ly:u8,lyc:u8,stat:u8,lcdc:u8,hvblank:u8,ime:u8,stable:u8,timer_flag:u8,
    remaining:i32,timer_phase:u32,budget:u32,lcd_count:u32,lcd_long:u32,timer_count:u32,
}
impl Clock {const EMPTY:Self=Self{advance:0,frame:0,pc:0,state:0,kind:0,div:0,elapsed:0,tima:0,tma:0,tac:0,ie:0,iflag:0,
    ly:0,lyc:0,stat:0,lcdc:0,hvblank:0,ime:0,stable:0,timer_flag:0,remaining:0,timer_phase:0,budget:0,lcd_count:0,lcd_long:0,timer_count:0};}
static mut ROWS:[Clock;CAP]=[Clock::EMPTY;CAP];
static mut ACTIVE:bool=false;
static mut READY:bool=false;
static mut IO:u32=0;
static mut TARGET:u32=0;
static mut LAST_FRAME:u32=u32::MAX;
static mut LEN:usize=0;
static mut DROPPED:u32=0;
static mut LCD:u32=0;
static mut LCD_LONG:u32=0;
static mut TIMER:u32=0;
#[cfg(not(test))]
#[inline] unsafe fn byte(a:u32)->u8 {core::ptr::read_volatile(a as *const u8)}
#[cfg(test)]
#[inline] unsafe fn byte(a:u32)->u8 {pnp::test_byte(a)}
#[cfg(not(test))]
#[inline] unsafe fn word(a:u32)->u32 {core::ptr::read_volatile(a as *const u32)}
#[cfg(test)]
#[inline] unsafe fn word(a:u32)->u32 {u32::from_le_bytes([byte(a),byte(a+1),byte(a+2),byte(a+3)])}
pub fn arm(target:u32,io:u32,valid:bool) {unsafe{
    ACTIVE=valid;READY=valid;IO=io;TARGET=target;LAST_FRAME=u32::MAX;LEN=0;DROPPED=0;LCD=0;LCD_LONG=0;TIMER=0;
}}
// Last delivered collector FRAME, not a hardware interrupt/frame counter.
pub fn frame(index:u32){unsafe{if ACTIVE {LAST_FRAME=index;}}}
pub fn ready()->bool {unsafe{READY}}
pub fn finish(){unsafe{ACTIVE=false;}}
pub fn observe(advance:u32,pc:u16,requested:u32) {unsafe{
    if !ACTIVE {return;}
    if requested==0xffc6 && pc==0x0554 {LCD=LCD.saturating_add(1);if byte(IO+0xc6)!=0 {LCD_LONG=LCD_LONG.saturating_add(1);}return;}
    let kind=if requested==0xff04 && matches!(pc,0x02b5|0x02b6|0x02bd|0x02be|0x2f60|0x2f68) {1}
        else if requested==0xffe9 && pc==0x3e25 {TIMER=TIMER.saturating_add(1);2}
        else {return;};
    if LEN>=CAP {DROPPED=DROPPED.saturating_add(1);return;}
    let s=&mut *core::ptr::addr_of_mut!(ROWS).cast::<Clock>().add(LEN);
    s.advance=advance;s.frame=LAST_FRAME;s.pc=pc;s.kind=kind;
    s.div=byte(IO+4);s.elapsed=byte(0x22f604);s.remaining=word(0x22fa50) as i32;
    s.timer_phase=word(0x22fa48);s.budget=word(0x22f600);
    s.state=((byte(IO+0xe1) as u16)<<8)|byte(IO+0xe2) as u16;
    s.tima=byte(IO+5);s.tma=byte(IO+6);s.tac=byte(IO+7);s.ie=byte(IO+255);s.iflag=byte(IO+15);
    s.ly=byte(IO+0x44);s.lyc=byte(IO+0x45);s.stat=byte(IO+0x41);s.lcdc=byte(IO+0x40);
    s.hvblank=byte(IO+0x9e);s.ime=byte(0x22f608);s.timer_flag=byte(IO+0xe9);
    s.lcd_count=LCD;s.lcd_long=LCD_LONG;s.timer_count=TIMER;
    s.stable=(s.div==byte(IO+4) && s.elapsed==byte(0x22f604) && s.remaining==word(0x22fa50) as i32) as u8;
    LEN+=1;
}}
pub fn save(){unsafe{
    let mut line=String::with_capacity(320);
    let _=write!(line,"\nR7110_CLOCKMETA,{},{},{},{},{},{},{},DIAGNOSTIC_NO_SHINY_GATE\n",TARGET,READY as u8,LEN,DROPPED,LCD,LCD_LONG,TIMER);
    pnp::trace_file_write(line.as_bytes());
    pnp::trace_file_write(b"record,index,kind,advance,frame,pc,state,div,elapsed,remaining,tima,tma,tac,ie,iflag,ly,lyc,stat,lcdc,hvblank,ime,timer_phase,budget,lcd_count,lcd_long,timer_count,timer_flag,stable\n");
    for i in 0..LEN {
        let s=&ROWS[i];line.clear();
        let _=write!(line,"R7110_CLOCK,{},{},{},{},{:04X},{:04X},{:02X},{},{},{:02X},{:02X},{:02X},{:02X},{:02X},{},{},{:02X},{:02X},{},{},{},{},{},{},{},{},{}\n",
            i,if s.kind==1 {"DIV"}else{"TIMER"},s.advance,s.frame,s.pc,s.state,s.div,s.elapsed,s.remaining,s.tima,s.tma,s.tac,s.ie,s.iflag,
            s.ly,s.lyc,s.stat,s.lcdc,s.hvblank,s.ime,s.timer_phase,s.budget,s.lcd_count,s.lcd_long,s.timer_count,s.timer_flag,s.stable);
        pnp::trace_file_write(line.as_bytes());
    }
}}
