//! Frozen VC state for strict native replay. No guest writes or live hooks.
use crate::pnp;
use alloc::string::String;
use core::fmt::Write;
const PAGE:usize=4096;
const STATIC_BASE:u32=0x001b1000;
const STATIC_PAGES:usize=0x14f; // through 002fffff; prefix code is already saved.
const HEAP_PAGES:usize=256;
const PAGES:usize=STATIC_PAGES+HEAP_PAGES;
static mut DATA:[u8;PAGES*PAGE]=[0;PAGES*PAGE];
static mut PRESENT:[bool;PAGES]=[false;PAGES];
static mut HEAP:u32=0;
static mut TARGET:u32=0;
static mut VALID:bool=false;
static mut CAPTURED:bool=false;
#[cfg(not(test))]
unsafe fn byte(a:u32)->u8 {core::ptr::read_volatile(a as *const u8)}
#[cfg(test)]
unsafe fn byte(a:u32)->u8 {pnp::test_byte(a)}
unsafe fn word(a:u32)->u32 {u32::from_le_bytes([byte(a),byte(a+1),byte(a+2),byte(a+3)])}
fn base(i:usize,heap:u32)->u32 {if i<STATIC_PAGES {STATIC_BASE+i as u32*PAGE as u32}else{heap+(i-STATIC_PAGES) as u32*PAGE as u32}}
unsafe fn captured_byte(a:u32)->Option<u8> {
    let off=if (STATIC_BASE..0x00300000).contains(&a) {(a-STATIC_BASE) as usize}
        else if a>=HEAP && a<HEAP+0x100000 {STATIC_PAGES*PAGE+(a-HEAP) as usize}
        else {return None};
    if PRESENT[off/PAGE] {Some(DATA[off])}else{None}
}
unsafe fn same(a:u32,n:usize)->bool {(0..n).all(|i|captured_byte(a+i as u32)==Some(byte(a+i as u32)))}
pub fn capture(target:u32,enabled:bool)->bool {unsafe{
    CAPTURED=false;VALID=false;PRESENT=[false;PAGES];TARGET=target;
    if !enabled {return true;}
    let wram=word(0x22f6c8);HEAP=wram&0xfff00000;
    if HEAP<0x08000000 || HEAP>=0x14000000 {return false;}
    for i in 0..PAGES {
        let a=base(i,HEAP);
        if !pnp::is_memory_mapped(a) || !pnp::is_memory_mapped(a+PAGE as u32-1) {continue;}
        pnp::read_into_raw(a,core::ptr::addr_of_mut!(DATA).cast::<u8>().add(i*PAGE),PAGE);
        PRESENT[i]=true;
    }
    CAPTURED=true;
    let io=word(0x22f6d8).wrapping_sub(128);
    // Current guest state must still equal the frozen page image. All three
    // native IO tables must be readable from the saved heap image.
    VALID=same(0x22f5e0,0x480)&&same(wram,8192)&&same(io,256);
    for ptr in [0x22f77c,0x22f780,0x22f784] {
        let a=word(ptr);
        VALID=VALID && a.checked_add(255).is_some() && (0..256).all(|i|captured_byte(a+i).is_some());
    }
    VALID
}}
fn hash(data:&[u8])->u32 {data.iter().fold(2166136261u32,|h,b|(h^(*b as u32)).wrapping_mul(16777619))}
pub fn save(){unsafe{
    if !CAPTURED {return;}
    let count=PRESENT.iter().filter(|x|**x).count();
    let mut line=String::with_capacity(1100);
    let _=write!(line,"\nR7111_SNAPSHOT,1,{},{},{:08X},{},{},{},FROZEN_NATIVE_STATE_NO_SHINY_GATE\n",TARGET,VALID as u8,HEAP,PAGES,count,PAGE);
    pnp::trace_file_write(line.as_bytes());
    for i in 0..PAGES {
        let a=base(i,HEAP);line.clear();
        let bytes=&DATA[i*PAGE..(i+1)*PAGE];
        let digest=if PRESENT[i] {hash(bytes)}else{0};
        let _=write!(line,"R7111_PAGE,{},{:08X},{},{:08X}\n",i,a,PRESENT[i] as u8,digest);
        pnp::trace_file_write(line.as_bytes());
        if !PRESENT[i] {continue;}
        for (chunk,b) in bytes.chunks(512).enumerate() {
            line.clear();let _=write!(line,"R7111_DATA,{},{},",i,chunk*512);
            for value in b {let _=write!(line,"{:02X}",value);}
            line.push('\n');pnp::trace_file_write(line.as_bytes());
        }
    }
    line.clear();let _=write!(line,"R7111_SNAPSHOT_END,{},{},{}\n",TARGET,count,count*PAGE);
    pnp::trace_file_write(line.as_bytes());
}}
