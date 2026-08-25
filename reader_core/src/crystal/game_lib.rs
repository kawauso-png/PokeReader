use crate::pnp;
use crate::title::{loaded_title, LoadedTitle};
use crate::utils::game_fn;

// GB memory read dispatcher.
// International: 0x1690b0. Japanese (0004000000172500): 0x169018, verified
// against the decrypted .code (lsr r1, r0, #12 / cmp r1, #0x10 /
// ldrlo pc, [pc, r1, lsl #2]).
game_fn!(read_gb_mem_intl(gb_addr: u32) -> u8 = 0x1690b0);
game_fn!(read_gb_mem_dispatch_jp(gb_addr: u32) -> u8 = 0x169018);

// On the Japanese release the dispatcher's 0xD000-0xDFFF handler reads through
// a pointer at 0x22f768 that appears to be stale outside CPU execution: every
// read in that range comes back as 0 while HRAM and IO reads are correct.
// The 0xC000-0xCFFF handler uses a separate pointer at 0x22f6c8, and WRAM is
// laid out contiguously, so banked WRAM is reachable at bank0 + 0x1000.
const JP_WRAM_BANK0_PTR: u32 = 0x0022f6c8;

fn read_gb_mem_jp(gb_addr: u32) -> u8 {
    if (0xD000..0xE000).contains(&gb_addr) {
        let base = pnp::read::<u32>(JP_WRAM_BANK0_PTR);
        if base != 0 {
            return pnp::read::<u8>(base + 0x1000 + (gb_addr - 0xD000));
        }
    }
    read_gb_mem_dispatch_jp(gb_addr)
}

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
