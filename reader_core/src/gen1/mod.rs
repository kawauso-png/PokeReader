use crate::pnp;

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_probe_step() -> u32;
    fn host_blue_probe_cursor() -> u32;
    fn host_blue_probe_passes() -> u32;
    fn host_blue_probe_hits() -> u32;
    fn host_blue_probe_source() -> u32;
    fn host_blue_probe_candidate() -> u32;
    fn host_blue_probe_dv() -> u32;
}

pub fn init_blue() {}

// Keep the C ABI expected by the known-good Blue framebuffer hook. Stage 4 is
// observational only; the new C probe scans host-state pointer VALUES and only
// tests candidates after svcQueryMemory says all fingerprint bytes are mapped.
#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
    0
}

pub fn run_frame() {
    pnp::set_print_max_len(31);

    let found = unsafe { host_blue_probe_step() };
    let cursor = unsafe { host_blue_probe_cursor() };
    let passes = unsafe { host_blue_probe_passes() };
    let hits = unsafe { host_blue_probe_hits() };
    let source = unsafe { host_blue_probe_source() };
    let candidate = unsafe { host_blue_probe_candidate() };
    let dv = unsafe { host_blue_probe_dv() };

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
        pnp::println!(color = 0x005FFF, "BLUE MINIMAL STAGE4");
        pnp::println!("reverse pointer probe");
        pnp::println!("HostF {}", HOST_FRAME);

        if found != 0 {
            pnp::println!(color = 0x00CC00, "WRAM FOUND {:08X}", found);
            pnp::println!("SRC {:08X}", source);
            pnp::println!("SIG 01 83 83 46");
            pnp::println!("DV {:04X}", dv & 0xFFFF);
            pnp::println!("FOUND locked");
        } else {
            pnp::println!("Host 00200000-00400000");
            pnp::println!("Scan {:08X} P{}", cursor, passes);
            pnp::println!("Ptr hits {}", hits);
            pnp::println!("Last {:08X}", candidate);
            pnp::println!("Keep Mewtwo battle open");
        }
    }
}
