use crate::pnp;

/// Emulator region base pointers found in the Japanese build's .data segment.
/// Each entry is the address of a global that holds a pointer to a GB memory
/// region, plus the GB address that region is mapped at.
const PRESETS: &[(&str, u32, u32)] = &[
    ("WRAMb 768", 0x0022f768, 0xd000),
    ("VRAM 768+4", 0x0022f76c, 0x8000),
    ("WRAM0 6C8", 0x0022f6c8, 0xc000),
    ("HRAM 6D8", 0x0022f6d8, 0xff80),
    ("IO 6DC", 0x0022f6dc, 0xff00),
    ("ROMn 634", 0x0022f634, 0x4000),
    ("ROM0 6C4", 0x0022f6c4, 0x0000),
    ("OAM 6D4", 0x0022f6d4, 0xfe00),
    ("SRAM 7F4", 0x0022f7f4, 0xa000),
];

/// Only dereference values that land in ranges the 3DS actually maps for an
/// application. Anything else is skipped so a bad pointer can't fault.
fn plausible(ptr: u32) -> bool {
    (0x00100000..0x08000000).contains(&ptr)
        || (0x0c000000..0x20000000).contains(&ptr)
        || (0x30000000..0x38000000).contains(&ptr)
}

#[derive(Default)]
pub struct MemView {
    preset: usize,
    offset: i64,
    step_shift: u32,
    found: Option<i64>,
    searched: bool,
}

impl MemView {
    fn step(&self) -> i64 {
        1i64 << (self.step_shift * 4)
    }

    fn base(&self) -> u32 {
        let slot = PRESETS[self.preset].1;
        pnp::read::<u32>(slot)
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
            self.found = None;
            self.searched = false;
        } else if pnp::is_just_pressed(pnp::Button::B) {
            self.search();
        }
    }

    /// Look for the trainer id pattern near the selected base.
    /// Gen 2 stores the id big endian, so 23264 is the byte pair 5A E0.
    fn search(&mut self) {
        let base = self.base();
        self.searched = true;
        self.found = None;

        if !plausible(base) {
            return;
        }

        let start = base.saturating_sub(0x8000);
        let end = base.saturating_add(0x8000);
        let mut addr = start;
        while addr < end {
            if plausible(addr) && pnp::read::<u8>(addr) == 0x5a && pnp::read::<u8>(addr + 1) == 0xe0
            {
                self.found = Some(addr as i64 - base as i64);
                return;
            }
            addr += 1;
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
        pnp::println!("off  {}{:X}", if self.offset < 0 { "-" } else { "+" }, self.offset.abs());
        pnp::println!("step {:X}", self.step());
        pnp::println!("");

        if !plausible(addr) {
            pnp::println!("addr {:08X}", addr);
            pnp::println!("out of range");
        } else {
            for row in 0..6u32 {
                let a = addr.wrapping_add(row * 4);
                pnp::println!(
                    "{:04X} {:02X}{:02X}{:02X}{:02X}",
                    a & 0xffff,
                    pnp::read::<u8>(a),
                    pnp::read::<u8>(a + 1),
                    pnp::read::<u8>(a + 2),
                    pnp::read::<u8>(a + 3)
                );
            }
        }

        pnp::println!("");
        match (self.searched, self.found) {
            (false, _) => pnp::println!("[B] find 5AE0"),
            (true, Some(off)) => pnp::println!("hit {}{:X}", if off < 0 { "-" } else { "+" }, off.abs()),
            (true, None) => pnp::println!("no hit"),
        }
        pnp::println!("X+Y then ^v <> A B");
    }
}
