// rel = advance - armed_target - 1, the existing CSV convention.
pub const FRAME_CAP: usize = 384;
pub const DEEP_CAP: usize = 32;
pub const CENTERS: &[u32] = &[
    42,222,225,231,238,241,247,254,257,263,270,343,350,359,366,369,
    391,398,407,414,423,430,439,446,526,535,542,551,577,606,615,
    622,631,638,647,654,702,715,
];
pub fn wants_frame(rel:u32)->bool {
    rel <= 42 || (713..=760).contains(&rel)
        || CENTERS.iter().any(|&c|rel>=c-1 && rel<=c+1)
}
pub fn is_div_pc(pc:u16)->bool {
    matches!(pc,0x02b5|0x02b6|0x02bd|0x02be|0x2f60|0x2f68)
}
