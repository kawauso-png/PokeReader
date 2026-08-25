use crate::title::{loaded_title, LoadedTitle};
use crate::utils::game_fn;

// GB memory read dispatcher.
// International: 0x1690b0.
// Japanese (0004000000172500): 0x169018, verified against the decrypted .code
// (lsr r1, r0, #12 / cmp r1, #0x10 / ldrlo pc, [pc, r1, lsl #2]).
game_fn!(read_gb_mem_intl(gb_addr: u32) -> u8 = 0x1690b0);
game_fn!(read_gb_mem_jp(gb_addr: u32) -> u8 = 0x169018);

fn read_gb_mem(gb_addr: u32) -> u8 {
    match loaded_title() {
        Ok(LoadedTitle::CrystalJp) => read_gb_mem_jp(gb_addr),
        _ => read_gb_mem_intl(gb_addr),
    }
}

pub mod gb_mem {
    use super::*;

    pub fn read_u8(addr: u32) -> u8 {
        read_gb_mem(addr)
    }

    pub fn read_u16(addr: u32) -> u16 {
        (read_u8(addr) as u16) << 8 | read_u8(addr + 1) as u16
    }

    pub fn read_u32(addr: u32) -> u32 {
        (read_u16(addr) as u32) << 16 | read_u16(addr + 2) as u32
    }
}
