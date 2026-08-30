use crate::pnp;

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

const WRAM0_PTR_SLOT: u32 = 0x0022_F6C8;
const HRAM_PTR_SLOT: u32 = 0x0022_F6D8;
const DIV_PTR_SLOT: u32 = 0x0022_F794;

static mut HOST_FRAME: u32 = 0;

pub fn init_blue() {}

// Keep the C ABI expected by the hardware-booted #164 main.c. Stage 2 still
// performs no encounter action and never dereferences a pointer candidate.
#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
    0
}

pub fn run_frame() {
    pnp::set_print_max_len(31);

    // These reads are intercepted by the Blue-specific C diagnostic path.
    // C prints the raw fixed-slot values, validates the candidate memory state,
    // and returns 0 unless an old 08Bxxxxx candidate is both mapped and stable.
    // Stage 2 never reads through the returned candidate.
    let safe_w = pnp::read::<u32>(WRAM0_PTR_SLOT);
    let safe_h = pnp::read::<u32>(HRAM_PTR_SLOT);
    let safe_d = pnp::read::<u32>(DIV_PTR_SLOT);

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
        pnp::println!(color = 0x005FFF, "BLUE MINIMAL STAGE2");
        pnp::println!("mapped-state gate fixed");
        pnp::println!("HostF {}", HOST_FRAME);
        pnp::println!("SAFE W {:08X}", safe_w);
        pnp::println!("SAFE H {:08X}", safe_h);
        pnp::println!("SAFE D {:08X}", safe_d);
        pnp::println!("No candidate dereference");
    }
}
