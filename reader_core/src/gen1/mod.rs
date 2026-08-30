use crate::pnp;

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_stage5_sample() -> u32;
    fn host_blue_stage5_wram_source() -> u32;
    fn host_blue_stage5_wram() -> u32;
    fn host_blue_stage5_hram_slot() -> u32;
    fn host_blue_stage5_hram() -> u32;
    fn host_blue_stage5_div_slot() -> u32;
    fn host_blue_stage5_div() -> u32;
    fn host_blue_stage5_rng_pack() -> u32;
    fn host_blue_stage5_div_value() -> u32;
    fn host_blue_stage5_frame_changes() -> u32;
    fn host_blue_stage5_div_changes() -> u32;
}

pub fn init_blue() {}

// Keep the C ABI expected by the known-good Blue framebuffer hook. Stage 5 is
// observational only: it re-reads the Stage-4 WRAM source and tests the old
// structure-relative +0x10 HRAM / +0xCC DIV slot offsets safely.
#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
    0
}

pub fn run_frame() {
    pnp::set_print_max_len(31);

    let status = unsafe { host_blue_stage5_sample() };
    let wsrc = unsafe { host_blue_stage5_wram_source() };
    let wram = unsafe { host_blue_stage5_wram() };
    let hslot = unsafe { host_blue_stage5_hram_slot() };
    let hram = unsafe { host_blue_stage5_hram() };
    let dslot = unsafe { host_blue_stage5_div_slot() };
    let div_ptr = unsafe { host_blue_stage5_div() };
    let rng = unsafe { host_blue_stage5_rng_pack() };
    let div_value = unsafe { host_blue_stage5_div_value() } as u8;
    let fchg = unsafe { host_blue_stage5_frame_changes() };
    let dchg = unsafe { host_blue_stage5_div_changes() };

    let wsrc_ok = status & (1 << 0) != 0;
    let wsig_ok = status & (1 << 1) != 0;
    let hslot_ok = status & (1 << 2) != 0;
    let hram_ok = status & (1 << 3) != 0;
    let dslot_ok = status & (1 << 4) != 0;
    let div_ok = status & (1 << 5) != 0;

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
        pnp::println!(color = 0x005FFF, "BLUE MINIMAL STAGE5");
        pnp::println!("recovered struct offsets");
        pnp::println!("HostF {} ST {:02X}", HOST_FRAME, status & 0x3F);

        pnp::println!(
            color = if wsrc_ok && wsig_ok { 0x00CC00 } else { 0xFF0000 },
            "W {:08X}>{:08X}",
            wsrc,
            wram
        );
        pnp::println!("W SIG {}", if wsig_ok { "01 83 83 46" } else { "FAIL" });

        pnp::println!(
            color = if hslot_ok && hram_ok { 0x00CC00 } else { 0xFF0000 },
            "H {:08X}>{:08X}",
            hslot,
            hram
        );
        if hram_ok {
            let add = ((rng >> 16) & 0xFF) as u8;
            let sub = ((rng >> 8) & 0xFF) as u8;
            let frame = (rng & 0xFF) as u8;
            pnp::println!("R {:02X}{:02X} F{:02X} ch{}", add, sub, frame, fchg);
        } else {
            pnp::println!(color = 0xFF0000, "R ---- F-- unmapped");
        }

        pnp::println!(
            color = if dslot_ok && div_ok { 0x00CC00 } else { 0xFF0000 },
            "D {:08X}>{:08X}",
            dslot,
            div_ptr
        );
        if div_ok {
            pnp::println!("DIV {:02X} ch{}", div_value, dchg);
        } else {
            pnp::println!(color = 0xFF0000, "DIV -- unmapped");
        }

        if wsig_ok && hram_ok && div_ok {
            pnp::println!(color = 0x00CC00, "STRUCT MATCH candidate");
        } else {
            pnp::println!("Keep Mewtwo battle open");
        }
    }
}
