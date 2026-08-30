pub const CAP: usize = 2048;

#[repr(C)]
#[derive(Clone, Copy)]
pub struct BootRow {
    pub seq: u32,
    pub rng: u32,
    pub div: u8,
    pub status: u8,
    pub valid: u8,
    pub first: u8,
    pub second: u8,
    pub k: u8,
    pub div_step: u8,
    pub gap: u8,
}

const EMPTY: BootRow = BootRow {
    seq: 0,
    rng: 0,
    div: 0,
    status: 0,
    valid: 0,
    first: 0,
    second: 0,
    k: 0,
    div_step: 0,
    gap: 0xFF,
};

#[derive(Clone, Copy, Default)]
pub struct BootStats {
    pub count: u32,
    pub valid: u32,
    pub invalid: u32,
    pub last_k: u8,
    pub last_step: u8,
    pub last_gap: u8,
}

static mut RING: [BootRow; CAP] = [EMPTY; CAP];
static mut ARM_ROWS: [BootRow; CAP] = [EMPTY; CAP];
static mut HEAD: usize = 0;
static mut COUNT: usize = 0;
static mut LIVE_VALID: u32 = 0;
static mut LIVE_INVALID: u32 = 0;
static mut ARM_COUNT: u32 = 0;
static mut ARM_VALID: u32 = 0;
static mut ARM_INVALID: u32 = 0;
static mut LAST_K: u8 = 0;
static mut LAST_STEP: u8 = 0;
static mut LAST_GAP: u8 = 0xFF;

fn rng_add(rng: u32) -> u8 { ((rng >> 16) & 0xFF) as u8 }
fn rng_sub(rng: u32) -> u8 { ((rng >> 8) & 0xFF) as u8 }

fn infer_vblank(prev_rng: u32, current_rng: u32) -> Option<(u8, u8, u8)> {
    let add0 = rng_add(prev_rng);
    let sub0 = rng_sub(prev_rng);
    let add1 = rng_add(current_rng);
    let sub1 = rng_sub(current_rng);
    let first = add1.wrapping_sub(add0);
    let carry = u8::from((add0 as u16 + first as u16) > 0xFF);
    let second = sub0.wrapping_sub(sub1).wrapping_sub(carry);
    let gap = second.wrapping_sub(first);
    if gap <= 1 { Some((first, second, gap)) } else { None }
}

pub fn observe(
    prev_seq: u32,
    prev_rng: u32,
    prev_div: u8,
    seq: u32,
    rng: u32,
    div: u8,
    status: u32,
) -> BootStats {
    unsafe {
        if seq == 0 || (status & 0x07) != 0x07 || (status & (1 << 3)) != 0 {
            return stats();
        }

        let mut row = EMPTY;
        row.seq = seq;
        row.rng = rng;
        row.div = div;
        row.status = (status & 0xFF) as u8;

        if prev_seq != 0 && seq == prev_seq.wrapping_add(1) {
            let step = div.wrapping_sub(prev_div);
            row.div_step = step;
            if matches!(step, 0x12 | 0x13) {
                if let Some((first, second, gap)) = infer_vblank(prev_rng, rng) {
                    row.valid = 1;
                    row.first = first;
                    row.second = second;
                    row.gap = gap;
                    row.k = first.wrapping_sub(div);
                    LIVE_VALID = LIVE_VALID.wrapping_add(1);
                    LAST_K = row.k;
                    LAST_STEP = step;
                    LAST_GAP = gap;
                }
            }
        }
        if row.valid == 0 {
            LIVE_INVALID = LIVE_INVALID.wrapping_add(1);
        }

        RING[HEAD] = row;
        HEAD = (HEAD + 1) & (CAP - 1);
        if COUNT < CAP { COUNT += 1; }
        stats()
    }
}

pub fn mark_arm() {
    unsafe {
        ARM_COUNT = COUNT as u32;
        ARM_VALID = 0;
        ARM_INVALID = 0;
        let start = (HEAD + CAP - COUNT) & (CAP - 1);
        for i in 0..COUNT {
            let row = RING[(start + i) & (CAP - 1)];
            ARM_ROWS[i] = row;
            if row.valid != 0 { ARM_VALID = ARM_VALID.wrapping_add(1); }
            else { ARM_INVALID = ARM_INVALID.wrapping_add(1); }
        }
        for row in ARM_ROWS.iter_mut().take(CAP).skip(COUNT) {
            *row = EMPTY;
        }
    }
}

pub fn stats() -> BootStats {
    unsafe {
        BootStats {
            count: COUNT as u32,
            valid: LIVE_VALID,
            invalid: LIVE_INVALID,
            last_k: LAST_K,
            last_step: LAST_STEP,
            last_gap: LAST_GAP,
        }
    }
}

pub fn arm_count() -> u32 { unsafe { ARM_COUNT } }
pub fn arm_valid() -> u32 { unsafe { ARM_VALID } }
pub fn arm_invalid() -> u32 { unsafe { ARM_INVALID } }
pub fn arm_rows_ptr() -> *const BootRow {
    unsafe { core::ptr::addr_of!(ARM_ROWS) as *const BootRow }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn abi_is_16_bytes() {
        assert_eq!(core::mem::size_of::<BootRow>(), 16);
    }

    #[test]
    fn k_math_matches_known_normal_transition() {
        // Trace 0040 KOBS seq 1141: K=18, DIV step=12, gap=1.
        // Pick a synthetic transition whose inferred first = current DIV + 0x18.
        let prev_add = 0x10u8;
        let current_div = 0x40u8;
        let first = current_div.wrapping_add(0x18);
        let current_add = prev_add.wrapping_add(first);
        let carry = u8::from((prev_add as u16 + first as u16) > 0xFF);
        let second = first.wrapping_add(1);
        let prev_sub = 0xD0u8;
        let current_sub = prev_sub.wrapping_sub(second).wrapping_sub(carry);
        let prev_rng = ((prev_add as u32) << 16) | ((prev_sub as u32) << 8) | 1;
        let current_rng = ((current_add as u32) << 16) | ((current_sub as u32) << 8) | 5;
        let got = infer_vblank(prev_rng, current_rng).unwrap();
        assert_eq!(got, (first, second, 1));
        assert_eq!(first.wrapping_sub(current_div), 0x18);
    }
}
