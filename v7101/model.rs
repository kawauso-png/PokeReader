// Empirical, counterfactual PRE filter. A match is NOT a guaranteed shiny.
// 16 logs establish the 3 neutral steps, not state-independent encounter paths.
pub const ROOTS: &[u8; 8192] = include_bytes!("roots.bin");
pub fn root_candidate(state: u16) -> bool {
    ROOTS[(state as usize) >> 3] & (1u8 << (state & 7)) != 0
}
pub fn after_neutral3(state: u16) -> u16 {
    let total = ((state >> 8) as u32) + 450;
    let sub = (state as u8).wrapping_sub(451u16 as u8).wrapping_sub((total >> 8) as u8);
    (((total & 255) as u16) << 8) | sub as u16
}
pub fn arm_matches(root: u16, target: u16, delta: u32, ap: u16, sp: u16, neutral: u32) -> bool {
    root_candidate(root) && target == after_neutral3(root) && delta == 3
        && ap == 0x2a35 && sp == 0x2a40 && neutral == 3
}
