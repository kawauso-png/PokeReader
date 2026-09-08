//! Kernel RTC reference and host tick at PRE / physical-UP launch.
//! Guest read-only. No allocation, file IO or key modification while capturing.
use crate::pnp;
use alloc::string::String;
use core::fmt::Write;
const BASE:u32=0x1ff81000;
const SIZE:usize=4096;
#[derive(Clone,Copy)]
struct Capture {bytes:[u8;SIZE],begin:u64,end:u64,valid:bool,present:bool}
impl Capture {const EMPTY:Self=Self{bytes:[0;SIZE],begin:0,end:0,valid:false,present:false};}
static mut ROWS:[Capture;2]=[Capture::EMPTY;2];
static mut ENABLED:bool=false;
static mut MAPPED:bool=false;
static mut TARGET:u32=0;
#[cfg(not(test))]
unsafe fn byte(a:u32)->u8 {core::ptr::read_volatile(a as *const u8)}
#[cfg(test)]
unsafe fn byte(a:u32)->u8 {pnp::test_byte(a)}
unsafe fn word(a:u32)->u32 {u32::from_le_bytes([byte(a),byte(a+1),byte(a+2),byte(a+3)])}
unsafe fn capture(stage:usize)->bool {
    let s=&mut *core::ptr::addr_of_mut!(ROWS).cast::<Capture>().add(stage);
    s.present=true;s.valid=false;
    if !MAPPED {return false;}
    for _ in 0..3 {
        let version=word(BASE);s.begin=pnp::system_tick();
        pnp::read_into_raw(BASE,s.bytes.as_mut_ptr(),SIZE);
        s.end=pnp::system_tick();
        let copied=u32::from_le_bytes([s.bytes[0],s.bytes[1],s.bytes[2],s.bytes[3]]);
        if version==copied && version==word(BASE) && s.end>=s.begin {s.valid=true;break;}
    }
    s.valid
}
pub fn arm(target:u32,enabled:bool) {unsafe{
    ROWS=[Capture::EMPTY;2];TARGET=target;ENABLED=enabled;MAPPED=false;
    if enabled {MAPPED=pnp::is_memory_mapped(BASE)&&pnp::is_memory_mapped(BASE+SIZE as u32-1);capture(0);}
}}
#[no_mangle]
pub extern "C" fn suicune_rtc7112_launch()->u32 {unsafe{
    if !ENABLED {return 1;}
    if ROWS[1].valid {return 1;}
    capture(1) as u32
}}
pub fn save(){unsafe{
    if !ENABLED {return;}
    let mut line=String::with_capacity(1100);
    for stage in 0..2 {
        let s=&ROWS[stage];if !s.present {continue;}
        let hash=s.bytes.iter().fold(2166136261u32,|h,b|(h^(*b as u32)).wrapping_mul(16777619));
        line.clear();let _=write!(line,"\nR7112_RTC,1,{},{},{},{},{},1FF81000,4096,{:08X}\n",stage,TARGET,s.valid as u8,s.begin,s.end,hash);
        pnp::trace_file_write(line.as_bytes());
        for (i,b) in s.bytes.chunks(512).enumerate(){
            line.clear();let _=write!(line,"R7112_RTC_DATA,{},{},",stage,i*512);
            for v in b {let _=write!(line,"{:02X}",v);}line.push('\n');pnp::trace_file_write(line.as_bytes());
        }
        line.clear();let _=write!(line,"R7112_RTC_END,{},{}\n",stage,TARGET);pnp::trace_file_write(line.as_bytes());
    }
}}
