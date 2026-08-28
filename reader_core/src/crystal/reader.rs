use super::game_lib::gb_mem;
use super::pk2::Pk2;
use crate::pnp;

struct Gen2Addresses {
    div_ptr: u32,
    pc_reg_ptr: u32,
    gb_rng_ptr: u32,
    /// None on the Japanese release, which has no daylight saving setting.
    dst_ptr: Option<u32>,
    time_ptr: u32,
    time_day_ptr: u32,
    play_time_ptr: u32,
    trainer_id_ptr: u32,
    party_ptr: u32,
    wild_ptr: u32,
    egg_ptr: u32,
}

const CRYSTAL_ADDRESSES: Gen2Addresses = Gen2Addresses {
    div_ptr: 0x22f794,
    pc_reg_ptr: 0x22f5fc,
    gb_rng_ptr: 0xffe1,
    dst_ptr: Some(0xd4c2),
    time_ptr: 0xff94,
    time_day_ptr: 0xd4cb,
    play_time_ptr: 0xd4c5,
    trainer_id_ptr: 0xd47b,
    party_ptr: 0xdcdf,
    wild_ptr: 0xd206,
    egg_ptr: 0xdf7b,
};

// The Japanese release has a different WRAM layout: shorter name buffers and no
// daylight saving setting. The emulator side pointers are unchanged.
// Save data map: https://vs-prof-oak.hatenablog.com/entry/2024/03/02/134741
const CRYSTAL_JP_ADDRESSES: Gen2Addresses = Gen2Addresses {
    div_ptr: 0x22f794,
    pc_reg_ptr: 0x22f5fc,
    gb_rng_ptr: 0xffe1,
    dst_ptr: None,
    time_ptr: 0xff94,
    // wGameTimeHours d4b7-d4b8, so the low byte is d4b8, then minutes, seconds
    play_time_ptr: 0xd4b8,
    // wCurDay d4be-d4bf
    time_day_ptr: 0xd4be,
    // wPlayerID d48c-d48d
    trainer_id_ptr: 0xd48c,
    // wPartyMon1 dca5, same 0x30 stride as the international release
    party_ptr: 0xdca5,
    // wEnemyMon d237, confirmed from a live Celebi battle: species FB at d237,
    // moves at d239-d23c, DVs at d23d/d23e
    wild_ptr: 0xd237,
    egg_ptr: 0xdf7b,
};

pub struct Gen2Reader {
    addrs: &'static Gen2Addresses,
}

impl Gen2Reader {
    pub fn crystal() -> Self {
        let addrs = match crate::title::loaded_title() {
            Ok(crate::title::LoadedTitle::CrystalJp) => &CRYSTAL_JP_ADDRESSES,
            _ => &CRYSTAL_ADDRESSES,
        };
        Self { addrs }
    }

    /// Host-process pointer to the byte that backs the emulated rDIV register.
    /// The Japanese and international Crystal builds currently share the same
    /// pointer slot (0x22F794).  Keeping the resolved host pointer available
    /// is useful for diagnostics even though the current differential probe
    /// scans the emulator-state region directly.
    pub fn div_host_ptr(&self) -> u32 {
        pnp::read::<u32>(self.addrs.div_ptr)
    }

    pub fn div(&self) -> u8 {
        pnp::read(self.div_host_ptr())
    }

    pub fn pc_reg(&self) -> u16 {
        pnp::read(self.addrs.pc_reg_ptr)
    }

    pub fn party(&self, slot: u8) -> Pk2 {
        let poke_addr = self.addrs.party_ptr + (slot as u32 * 0x30);
        let experience = gb_mem::read_u32(poke_addr + 0x8);
        let atkdef = gb_mem::read_u8(poke_addr + 0x15);
        let spespc = gb_mem::read_u8(poke_addr + 0x16);
        let spec_index = gb_mem::read_u8(poke_addr);
        Pk2::new(spec_index, atkdef, spespc, experience)
    }

    pub fn wild(&self) -> Pk2 {
        let spec_index = gb_mem::read_u8(self.addrs.wild_ptr);
        let atkdef = gb_mem::read_u8(self.addrs.wild_ptr + 0x6);
        let spespc = gb_mem::read_u8(self.addrs.wild_ptr + 0x7);
        Pk2::new(spec_index, atkdef, spespc, 0)
    }

    pub fn egg(&self) -> Pk2 {
        let spec_index = gb_mem::read_u8(self.addrs.egg_ptr);
        let atkdef = gb_mem::read_u8(self.addrs.egg_ptr + 0x15);
        let spespc = gb_mem::read_u8(self.addrs.egg_ptr + 0x16);
        Pk2::new(spec_index, atkdef, spespc, 0)
    }

    pub fn rng_state(&self) -> u16 {
        gb_mem::read_u16(self.addrs.gb_rng_ptr)
    }

    pub fn time_seconds(&self) -> u8 {
        gb_mem::read_u8(self.addrs.time_ptr + 4)
    }

    pub fn time_minutes(&self) -> u8 {
        gb_mem::read_u8(self.addrs.time_ptr + 2)
    }

    pub fn time_hours(&self) -> u8 {
        gb_mem::read_u8(self.addrs.time_ptr)
    }

    pub fn time_day(&self) -> u8 {
        gb_mem::read_u8(self.addrs.time_day_ptr) % 7
    }

    pub fn play_seconds(&self) -> u8 {
        gb_mem::read_u8(self.addrs.play_time_ptr + 2)
    }

    pub fn play_minutes(&self) -> u8 {
        gb_mem::read_u8(self.addrs.play_time_ptr + 1)
    }

    pub fn play_hours(&self) -> u8 {
        gb_mem::read_u8(self.addrs.play_time_ptr)
    }

    pub fn dst(&self) -> bool {
        match self.addrs.dst_ptr {
            Some(ptr) => (gb_mem::read_u8(ptr) & 0x80) != 0,
            None => false,
        }
    }

    pub fn trainer_id(&self) -> u16 {
        gb_mem::read_u16(self.addrs.trainer_id_ptr)
    }
}
