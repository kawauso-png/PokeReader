use crate::pnp;

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

static mut HOST_FRAME: u32 = 0;

pub fn init_blue() {}

// Stage 1 deliberately disables the old target/pointer path while preserving
// the C ABI expected by the already hardware-booted #164 main.c.
#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
    0
}

pub fn run_frame() {
    pnp::set_print_max_len(31);

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
        pnp::println!(color = 0x005FFF, "BLUE MINIMAL STAGE1");
        pnp::println!("overlay hook alive");
        pnp::println!("HostF {}", HOST_FRAME);
        pnp::println!("No RNG / no pointers");
        pnp::println!("No Mewtwo logic yet");
    }
}
