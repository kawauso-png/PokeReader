use super::hook;
use crate::pnp;

/// Emulator region base pointers in the Japanese build's .data segment:
/// (label, address of the global, GB address the region is mapped at).
const PRESETS: &[(&str, u32, u32, i64)] = &[
    // Bookmarks into WRAM, so the interesting blocks can be reached with A
    // instead of thousands of d-pad presses. The offset is from the region base.
    ("ROM0 6C4", 0x0022f6c4, 0x0000, 0),
    ("gb D480", 0x0022f6c8, 0xc000, 0x1480),
    ("gb D4A0", 0x0022f6c8, 0xc000, 0x14a0),
    ("gb D4C0", 0x0022f6c8, 0xc000, 0x14c0),
    ("gb D4E0", 0x0022f6c8, 0xc000, 0x14e0),
    ("gb DC90", 0x0022f6c8, 0xc000, 0x1c90),
    ("gb DCB0", 0x0022f6c8, 0xc000, 0x1cb0),
    // Raw region pointers
    ("WRAM0 6C8", 0x0022f6c8, 0xc000, 0),
    ("WRAMb 768", 0x0022f768, 0xd000, 0),
    ("HRAM 6D8", 0x0022f6d8, 0xff80, 0),
    ("IO 6DC", 0x0022f6dc, 0xff00, 0),
    ("SRAM 7F4", 0x0022f7f4, 0xa000, 0),
];

/// Trainer id 23264, stored big endian by gen 2.
const NEEDLE: [u8; 2] = [0x5a, 0xe0];

/// The VBlank RNG update, as raw GB opcodes:
///   ldh a,[rDIV] / ld b,a / ldh a,[hRandomAdd] / adc b / ldh [hRandomAdd],a
///   ldh a,[rDIV] / ld b,a / ldh a,[hRandomSub] / sbc b / ldh [hRandomSub],a
/// PokeReader hooks the two rDIV reads by program counter, so finding this
/// pattern gives the two values it needs.
const RNG_PATTERN: [u8; 16] = [
    0xf0, 0x04, 0x47, 0xf0, 0xe1, 0x88, 0xe0, 0xe1, 0xf0, 0x04, 0x47, 0xf0, 0xe2, 0x98, 0xe0, 0xe2,
];

/// Ranges the 3ds actually maps for an application. The emulator keeps its GB
/// regions around 0x08a3xxxx, so that block has to be included.
fn plausible(ptr: u32) -> bool {
    (0x00100000..0x0c000000).contains(&ptr) || (0x0c000000..0x40000000).contains(&ptr)
}

pub struct MemView {
    preset: usize,
    offset: i64,
    step_shift: u32,
    hits: [Option<u32>; 3],
    searched: bool,
}

impl Default for MemView {
    fn default() -> Self {
        Self {
            preset: 0,
            offset: PRESETS[0].3,
            step_shift: 0,
            hits: [None; 3],
            searched: false,
        }
    }
}

impl MemView {
    fn step(&self) -> i64 {
        1i64 << (self.step_shift * 4)
    }

    fn base(&self) -> u32 {
        pnp::read::<u32>(PRESETS[self.preset].1)
    }

    fn update(&mut self, is_locked: bool) {
        if !is_locked {
            return;
        }

        if pnp::is_just_pressed(pnp::Button::Ddown) {
            self.offset += self.step();
        } else if pnp::is_just_pressed(pnp::Button::Dup) {
            self.offset -= self.step();
        } else if pnp::is_just_pressed(pnp::Button::Dright) {
            self.step_shift = (self.step_shift + 1) % 6;
        } else if pnp::is_just_pressed(pnp::Button::Dleft) {
            self.step_shift = (self.step_shift + 5) % 6;
        } else if pnp::is_just_pressed(pnp::Button::A) {
            self.preset = (self.preset + 1) % PRESETS.len();
            self.offset = PRESETS[self.preset].3;
            self.hits = [None; 3];
            self.searched = false;
        } else if pnp::is_just_pressed(pnp::Button::B) {
            self.search();
        }
    }

    /// In ROM, look for the VBlank RNG update. In RAM, look for the trainer id.
    fn search(&mut self) {
        let base = self.base();
        let gb_base = PRESETS[self.preset].2;
        self.searched = true;
        self.hits = [None; 3];

        if !plausible(base) {
            return;
        }

        let rom = gb_base < 0x8000;
        let mut found = 0;
        let mut scanned = 0u32;
        while scanned < 0x8000 && found < 3 {
            let addr = base + scanned;
            let matched = if rom {
                (0..RNG_PATTERN.len() as u32).all(|i| pnp::read::<u8>(addr + i) == RNG_PATTERN[i as usize])
            } else {
                pnp::read::<u8>(addr) == NEEDLE[0] && pnp::read::<u8>(addr + 1) == NEEDLE[1]
            };
            if matched {
                self.hits[found] = Some(gb_base.wrapping_add(scanned));
                found += 1;
            }
            scanned += 1;
        }
    }

    pub fn update_and_draw(&mut self, is_locked: bool) {
        self.update(is_locked);

        let (seen1, seen2) = hook::pc_seen();
        pnp::println!("hook {}", hook::any_hits());
        pnp::println!("ff04 {}", hook::ff04_hits());
        let (alt, alt_ff04) = hook::alt_hits();
        pnp::println!("alt  {} / {}", alt, alt_ff04);
        pnp::println!("pc   {:04X}", hook::last_pc());
        pnp::println!("seen {:04X} {:04X}", seen1, seen2);
        pnp::println!("");

        let (name, slot, gb_addr, _) = PRESETS[self.preset];
        let base = self.base();
        let addr = (base as i64 + self.offset) as u32;

        pnp::println!("{}", name);
        pnp::println!("slot {:08X}", slot);
        pnp::println!("base {:08X}", base);
        pnp::println!("gb   {:04X}", gb_addr);
        pnp::println!(
            "off  {}{:X}  st {:X}",
            if self.offset < 0 { "-" } else { "+" },
            self.offset.abs(),
            self.step()
        );

        if plausible(addr) {
            pnp::println!("at gb {:04X}", gb_addr.wrapping_add(self.offset as u32));
            for row in 0..4u32 {
                let a = addr.wrapping_add(row * 4);
                pnp::println!(
                    "{:04X} {:02X}{:02X}{:02X}{:02X}",
                    (gb_addr.wrapping_add(self.offset as u32)).wrapping_add(row * 4) & 0xffff,
                    pnp::read::<u8>(a),
                    pnp::read::<u8>(a + 1),
                    pnp::read::<u8>(a + 2),
                    pnp::read::<u8>(a + 3)
                );
            }
        } else {
            pnp::println!("addr {:08X}", addr);
            pnp::println!("out of range");
        }

        pnp::println!("");
        let rom = gb_addr < 0x8000;
        if !self.searched {
            pnp::println!("[B] {}", if rom { "find RNG" } else { "find 5AE0" });
        } else {
            let mut any = false;
            for hit in self.hits.iter().flatten() {
                if rom {
                    // The two rDIV reads sit at +1 and +9 from the pattern start.
                    pnp::println!("RNG1 {:04X}", hit.wrapping_add(1));
                    pnp::println!("RNG2 {:04X}", hit.wrapping_add(9));
                } else {
                    pnp::println!("TID at gb {:04X}", hit);
                }
                any = true;
            }
            if !any {
                pnp::println!("no hit here");
            }
        }
        pnp::println!("A next  X+Y lock");
    }
}
