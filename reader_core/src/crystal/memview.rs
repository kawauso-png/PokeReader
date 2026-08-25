use crate::pnp;

/// Emulator region base pointers in the Japanese build's .data segment:
/// (label, address of the global, GB address the region is mapped at).
const PRESETS: &[(&str, u32, u32)] = &[
    ("WRAM0 6C8", 0x0022f6c8, 0xc000),
    ("WRAMb 768", 0x0022f768, 0xd000),
    ("HRAM 6D8", 0x0022f6d8, 0xff80),
    ("IO 6DC", 0x0022f6dc, 0xff00),
    ("SRAM 7F4", 0x0022f7f4, 0xa000),
    ("VRAM 768+4", 0x0022f76c, 0x8000),
    ("OAM 6D4", 0x0022f6d4, 0xfe00),
    ("ROM0 6C4", 0x0022f6c4, 0x0000),
    ("ROMn 634", 0x0022f634, 0x4000),
];

/// Trainer id 23264, stored big endian by gen 2.
const NEEDLE: [u8; 2] = [0x5a, 0xe0];

/// Ranges the 3ds actually maps for an application. The emulator keeps its GB
/// regions around 0x08a3xxxx, so that block has to be included.
fn plausible(ptr: u32) -> bool {
    (0x00100000..0x0c000000).contains(&ptr) || (0x0c000000..0x40000000).contains(&ptr)
}

#[derive(Default)]
pub struct MemView {
    preset: usize,
    offset: i64,
    step_shift: u32,
    hits: [Option<u32>; 3],
    searched: bool,
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
            self.offset = 0;
            self.hits = [None; 3];
            self.searched = false;
        } else if pnp::is_just_pressed(pnp::Button::B) {
            self.search();
        }
    }

    /// Scan the whole region the selected pointer covers and record where the
    /// trainer id sits, expressed as a GB address.
    fn search(&mut self) {
        let base = self.base();
        let gb_base = PRESETS[self.preset].2;
        self.searched = true;
        self.hits = [None; 3];

        if !plausible(base) {
            return;
        }

        let mut found = 0;
        let mut scanned = 0u32;
        while scanned < 0x8000 && found < 3 {
            let addr = base + scanned;
            if pnp::read::<u8>(addr) == NEEDLE[0] && pnp::read::<u8>(addr + 1) == NEEDLE[1] {
                self.hits[found] = Some(gb_base.wrapping_add(scanned));
                found += 1;
            }
            scanned += 1;
        }
    }

    pub fn update_and_draw(&mut self, is_locked: bool) {
        self.update(is_locked);

        let (name, slot, gb_addr) = PRESETS[self.preset];
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
            for row in 0..5u32 {
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
        if !self.searched {
            pnp::println!("[B] find 5AE0");
        } else {
            let mut any = false;
            for hit in self.hits.iter().flatten() {
                pnp::println!("TID at gb {:04X}", hit);
                any = true;
            }
            if !any {
                pnp::println!("no hit here");
            }
        }
        pnp::println!("A next  X+Y lock");
    }
}
