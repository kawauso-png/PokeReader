//! Experimental PRE-only ensemble. Scores are NOT probabilities.
//! Fixed observed paths + workload phase transport; no guest-memory writes.
const TABLE: &[u8] = include_bytes!("hunt_v7110.bin");
const STRIDE: usize = 8 + 512 + 32768;
const DONORS: usize = 10;
#[derive(Clone, Copy)]
pub struct Score { pub support:u32, pub score:u32, pub total:u32, pub first:u16, pub unique:u32 }
impl Score { pub const EMPTY:Self=Self{support:0,score:0,total:0,first:0,unique:0}; }
fn rd(i:usize)->u16 {(TABLE[i] as u16)|((TABLE[i+1] as u16)<<8)}
fn shiny(raw:u16)->bool {(raw&0x0fff)==0x0aaa && ((raw>>12)&2)!=0}
pub fn evaluate(state:u16,phase:u16,cycles:u16,bits:&mut [u8;8192])->Score {
    for b in bits.iter_mut(){*b=0;}
    let mut out=Score::EMPTY;
    if TABLE.len()!=STRIDE*DONORS || phase&63!=53 {return out;}
    let z0=((state>>8) as i32-256*((state&255) as i32))&65535;
    for d in 0..DONORS {
        let base=d*STRIDE;
        let shift=phase.wrapping_sub(rd(base+2))&0x3fff;
        if shift&63!=0 {continue;}
        let prefix=rd(base+8+2*((shift>>6) as usize)) as i32;
        let center=shift as i32+cycles as i32-rd(base) as i32;
        let mut donor_hit=false;
        for jitter in -80i32..=80i32 {
            let off=((center+jitter)&16383) as usize;
            let inc=prefix+rd(base+520+off*2) as i32;
            let za=(z0+inc)&65535;
            let last_a=(((rd(base+4) as i32+off as i32)&16383)>>6) as i32;
            let last_s=(((rd(base+6) as i32+off as i32)&16383)>>6) as i32;
            let carry=if (za&255)<last_a {1}else{0};
            let jw=if jitter.abs()<=16 {4u32}else{1u32};
            for err in -1i32..=1i32 {
                let lo=(-(za>>8)+err)&255;
                let hi=(lo+last_s+carry)&255;
                let raw=((hi<<8)|lo) as u16;
                let weight=jw*if err==0 {2}else{1};
                out.total+=weight;
                let bi=(raw as usize)>>3;let mask=1u8<<(raw&7);
                if bits[bi]&mask==0 {bits[bi]|=mask;out.unique+=1;}
                if shiny(raw) {
                    donor_hit=true;out.score+=weight;
                    if out.first==0 {out.first=raw;}
                }
            }
        }
        if donor_hit {out.support+=1;}
    }
    out
}
pub fn ready(s:Score)->bool {s.support>=2 && s.score>=16}
