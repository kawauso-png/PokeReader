use crate::pnp;

pub const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

static mut HOST_FRAME: u32 = 0;

extern "C" {
    fn host_blue_stage6_sample() -> u32;
    fn host_blue_stage6_samples() -> u32;
    fn host_blue_stage6_wram() -> u32;
    fn host_blue_stage6_hram() -> u32;
    fn host_blue_stage6_rng_pack() -> u32;

    fn host_blue_stage6_pred_slot() -> u32;
    fn host_blue_stage6_pred_raw() -> u32;
    fn host_blue_stage6_pred_value() -> u32;
    fn host_blue_stage6_pred_changes() -> u32;
    fn host_blue_stage6_pred_steps() -> u32;
    fn host_blue_stage6_pred_delta() -> u32;

    fn host_blue_stage6_best_inline_src() -> u32;
    fn host_blue_stage6_best_inline_value() -> u32;
    fn host_blue_stage6_best_inline_changes() -> u32;
    fn host_blue_stage6_best_inline_steps() -> u32;
    fn host_blue_stage6_best_inline_delta() -> u32;

    fn host_blue_stage6_best_ptr_src() -> u32;
    fn host_blue_stage6_best_ptr_target() -> u32;
    fn host_blue_stage6_best_ptr_value() -> u32;
    fn host_blue_stage6_best_ptr_changes() -> u32;
    fn host_blue_stage6_best_ptr_steps() -> u32;
    fn host_blue_stage6_best_ptr_delta() -> u32;
}

pub fn init_blue() {}

#[no_mangle]
pub extern "C" fn blue_capture_target(_run_id: u32) -> u32 {
    0
}

pub fn run_frame() {
    pnp::set_print_max_len(31);

    let status = unsafe { host_blue_stage6_sample() };
    let samples = unsafe { host_blue_stage6_samples() };
    let wram = unsafe { host_blue_stage6_wram() };
    let hram = unsafe { host_blue_stage6_hram() };
    let rng = unsafe { host_blue_stage6_rng_pack() };

    let pred_slot = unsafe { host_blue_stage6_pred_slot() };
    let pred_raw = unsafe { host_blue_stage6_pred_raw() };
    let pred_v = unsafe { host_blue_stage6_pred_value() } as u8;
    let pred_ch = unsafe { host_blue_stage6_pred_changes() };
    let pred_ds = unsafe { host_blue_stage6_pred_steps() };
    let pred_d = unsafe { host_blue_stage6_pred_delta() } as u8;

    let bi_src = unsafe { host_blue_stage6_best_inline_src() };
    let bi_v = unsafe { host_blue_stage6_best_inline_value() } as u8;
    let bi_ch = unsafe { host_blue_stage6_best_inline_changes() };
    let bi_ds = unsafe { host_blue_stage6_best_inline_steps() };
    let bi_d = unsafe { host_blue_stage6_best_inline_delta() } as u8;

    let bp_src = unsafe { host_blue_stage6_best_ptr_src() };
    let bp_tgt = unsafe { host_blue_stage6_best_ptr_target() };
    let bp_v = unsafe { host_blue_stage6_best_ptr_value() } as u8;
    let bp_ch = unsafe { host_blue_stage6_best_ptr_changes() };
    let bp_ds = unsafe { host_blue_stage6_best_ptr_steps() };
    let bp_d = unsafe { host_blue_stage6_best_ptr_delta() } as u8;

    let w_ok = status & (1 << 1) != 0;
    let h_ok = status & (1 << 3) != 0;
    let scan_ok = status & (1 << 4) != 0;

    unsafe {
        HOST_FRAME = HOST_FRAME.wrapping_add(1);
        pnp::println!(color = 0x005FFF, "BLUE MINIMAL STAGE6");
        pnp::println!("DIV inline/neighborhood probe");
        pnp::println!("HostF {} S{} ST{:02X}", HOST_FRAME, samples, status & 0x1F);
        pnp::println!(
            color = if w_ok && h_ok { 0x00CC00 } else { 0xFF0000 },
            "W {:08X} H {:08X}",
            wram,
            hram
        );

        if h_ok {
            let add = ((rng >> 16) & 0xFF) as u8;
            let sub = ((rng >> 8) & 0xFF) as u8;
            let frame = (rng & 0xFF) as u8;
            pnp::println!("R {:02X}{:02X} F{:02X}", add, sub, frame);
        }

        pnp::println!("Pred {:08X} raw {:08X}", pred_slot, pred_raw);
        pnp::println!("Plo {:02X} ch{} ds{} d{:02X}", pred_v, pred_ch, pred_ds, pred_d);

        if scan_ok {
            pnp::println!(color = 0x00CC00, "BestI {:08X} v{:02X}", bi_src, bi_v);
            pnp::println!("I ch{} ds{} d{:02X}", bi_ch, bi_ds, bi_d);

            if bp_src != 0 {
                pnp::println!("BestP {:08X}>{:08X}", bp_src, bp_tgt);
                pnp::println!("P v{:02X} ch{} ds{} d{:02X}", bp_v, bp_ch, bp_ds, bp_d);
            } else {
                pnp::println!("BestP none in neighborhood");
            }
        } else {
            pnp::println!(color = 0xFF0000, "DIV neighborhood unmapped");
        }

        pnp::println!("Wait 5 sec; send screenshot");
    }
}
