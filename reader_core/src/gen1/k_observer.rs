const K_RING_CAP: usize = 512;

#[repr(C)]
#[derive(Clone, Copy, Default)]
pub struct KObsRow {
    pub seq: u32,
    pub k: u8,
    pub div_step: u8,
    pub gap: u8,
    pub phase4: u8,
}

#[derive(Clone, Copy, Default)]
pub struct KObsStats {
    pub valid_total: u32,
    pub invalid_total: u32,
    pub ring_count: u16,
    pub unique: u16,
    pub mode_k: u8,
    pub mode_pct: u8,
    pub phase_mode: [u8; 4],
    pub phase_pct: [u8; 4],
}

static mut RING: [KObsRow; K_RING_CAP] = [KObsRow {
    seq: 0,
    k: 0,
    div_step: 0,
    gap: 0,
    phase4: 0,
}; K_RING_CAP];
static mut RING_HEAD: usize = 0;
static mut RING_COUNT: usize = 0;
static mut HIST: [u32; 256] = [0; 256];
static mut PHASE_HIST: [[u32; 256]; 4] = [[0; 256]; 4];
static mut VALID_TOTAL: u32 = 0;
static mut INVALID_TOTAL: u32 = 0;

static mut ARM_ROWS: [KObsRow; K_RING_CAP] = [KObsRow {
    seq: 0,
    k: 0,
    div_step: 0,
    gap: 0,
    phase4: 0,
}; K_RING_CAP];
static mut ARM_COUNT: usize = 0;
static mut ARM_VALID_TOTAL: u32 = 0;
static mut ARM_INVALID_TOTAL: u32 = 0;

fn rng_add(rng: u32) -> u8 {
    ((rng >> 16) & 0xFF) as u8
}

fn rng_sub(rng: u32) -> u8 {
    ((rng >> 8) & 0xFF) as u8
}

fn infer_vblank(prev_rng: u32, current_rng: u32) -> Option<(u8, u8)> {
    let add0 = rng_add(prev_rng);
    let sub0 = rng_sub(prev_rng);
    let add1 = rng_add(current_rng);
    let sub1 = rng_sub(current_rng);
    let first = add1.wrapping_sub(add0);
    let carry = u8::from((add0 as u16 + first as u16) > 0xFF);
    let second = sub0.wrapping_sub(sub1).wrapping_sub(carry);
    let gap = second.wrapping_sub(first);
    if gap <= 1 { Some((first, gap)) } else { None }
}

fn mode_u32(hist: &[u32; 256]) -> (u8, u32, u16) {
    let mut mode_k = 0u8;
    let mut mode_count = 0u32;
    let mut unique = 0u16;
    let mut i = 0usize;
    while i < 256 {
        let c = hist[i];
        if c != 0 {
            unique = unique.saturating_add(1);
            if c > mode_count {
                mode_count = c;
                mode_k = i as u8;
            }
        }
        i += 1;
    }
    (mode_k, mode_count, unique)
}

fn pct(part: u32, total: u32) -> u8 {
    if total == 0 {
        0
    } else {
        core::cmp::min(100, ((part.saturating_mul(100) + total / 2) / total) as u32) as u8
    }
}

pub fn observe(
    prev_seq: u32,
    prev_rng: u32,
    prev_div: u8,
    seq: u32,
    rng: u32,
    div: u8,
) {
    if prev_seq == 0 || seq != prev_seq.wrapping_add(1) {
        unsafe { INVALID_TOTAL = INVALID_TOTAL.wrapping_add(1); }
        return;
    }

    let div_step = div.wrapping_sub(prev_div);
    if !matches!(div_step, 0x12 | 0x13) {
        unsafe { INVALID_TOTAL = INVALID_TOTAL.wrapping_add(1); }
        return;
    }

    let Some((first, gap)) = infer_vblank(prev_rng, rng) else {
        unsafe { INVALID_TOTAL = INVALID_TOTAL.wrapping_add(1); }
        return;
    };

    let k = first.wrapping_sub(div);
    let phase4 = (seq & 3) as u8;
    let row = KObsRow {
        seq,
        k,
        div_step,
        gap,
        phase4,
    };

    unsafe {
        RING[RING_HEAD] = row;
        RING_HEAD = (RING_HEAD + 1) % K_RING_CAP;
        if RING_COUNT < K_RING_CAP {
            RING_COUNT += 1;
        }
        HIST[k as usize] = HIST[k as usize].wrapping_add(1);
        PHASE_HIST[phase4 as usize][k as usize] =
            PHASE_HIST[phase4 as usize][k as usize].wrapping_add(1);
        VALID_TOTAL = VALID_TOTAL.wrapping_add(1);
    }
}

pub fn stats() -> KObsStats {
    unsafe {
        let (mode_k, mode_count, unique) = mode_u32(&HIST);
        let mut phase_mode = [0u8; 4];
        let mut phase_pct = [0u8; 4];
        let mut p = 0usize;
        while p < 4 {
            let (mk, mc, _) = mode_u32(&PHASE_HIST[p]);
            let mut total = 0u32;
            let mut i = 0usize;
            while i < 256 {
                total = total.wrapping_add(PHASE_HIST[p][i]);
                i += 1;
            }
            phase_mode[p] = mk;
            phase_pct[p] = pct(mc, total);
            p += 1;
        }
        KObsStats {
            valid_total: VALID_TOTAL,
            invalid_total: INVALID_TOTAL,
            ring_count: RING_COUNT as u16,
            unique,
            mode_k,
            mode_pct: pct(mode_count, VALID_TOTAL),
            phase_mode,
            phase_pct,
        }
    }
}

pub fn mark_arm() {
    unsafe {
        let count = RING_COUNT;
        let oldest = (RING_HEAD + K_RING_CAP - count) % K_RING_CAP;
        let mut i = 0usize;
        while i < count {
            ARM_ROWS[i] = RING[(oldest + i) % K_RING_CAP];
            i += 1;
        }
        ARM_COUNT = count;
        ARM_VALID_TOTAL = VALID_TOTAL;
        ARM_INVALID_TOTAL = INVALID_TOTAL;
    }
}

pub fn arm_rows_ptr() -> *const KObsRow {
    core::ptr::addr_of!(ARM_ROWS) as *const KObsRow
}

pub fn arm_count() -> u32 {
    unsafe { ARM_COUNT as u32 }
}

pub fn arm_valid_total() -> u32 {
    unsafe { ARM_VALID_TOTAL }
}

pub fn arm_invalid_total() -> u32 {
    unsafe { ARM_INVALID_TOTAL }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn row_layout_is_c_compatible_size() {
        assert_eq!(core::mem::size_of::<KObsRow>(), 8);
    }

    #[test]
    fn infer_trace_0039_first_transition() {
        let prev_rng = 0xCD9E00u32;
        let rng = 0x036700u32;
        let (first, gap) = infer_vblank(prev_rng, rng).unwrap();
        assert_eq!(gap, 0);
        assert_eq!(first.wrapping_sub(0x1Eu8), 0x18);
    }

    #[test]
    fn mode_helpers_are_stable() {
        let mut h = [0u32; 256];
        h[0x0E] = 9;
        h[0x0F] = 3;
        let (k, count, unique) = mode_u32(&h);
        assert_eq!(k, 0x0E);
        assert_eq!(count, 9);
        assert_eq!(unique, 2);
        assert_eq!(pct(9, 12), 75);
    }
}
