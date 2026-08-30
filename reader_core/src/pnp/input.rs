use super::bindings;
use core::{
    cmp::PartialEq,
    ops::{BitAnd, BitOr},
};
use num_enum::IntoPrimitive;

const BLUE_JP_TITLE_ID: u64 = 0x0004_0000_0017_0E00;

/// A button that can be pressed by a user.
#[derive(Debug, Clone, Copy, PartialEq, Eq, IntoPrimitive)]
#[repr(u32)]
pub enum Button {
    A = 1,
    B = 2,
    Select = 4,
    Start = 8,
    Dright = 16,
    Dleft = 32,
    Dup = 64,
    Ddown = 128,
    R = 256,
    L = 512,
    X = 1024,
    Y = 2048,
}

impl PartialEq<Button> for u32 {
    fn eq(&self, other: &Button) -> bool {
        *self == *other as u32
    }
}

impl PartialEq<u32> for Button {
    fn eq(&self, other: &u32) -> bool {
        *self as u32 == *other
    }
}

impl BitAnd<Button> for u32 {
    type Output = u32;
    fn bitand(self, rhs: Button) -> Self::Output { self & (rhs as u32) }
}

impl BitOr for Button {
    type Output = u32;
    fn bitor(self, rhs: Self) -> Self::Output { (self as u32) | (rhs as u32) }
}

pub fn is_just_pressed(io_bits: impl Into<u32>) -> bool {
    let bits = io_bits.into();
    let title = unsafe { bindings::host_get_game_title_id() };

    // For Japanese VC Blue, A calibration must follow the Game Boy game's own
    // joypad edge, not the 3DS-side HID edge. Mewtwo requires A1 to talk and A2
    // after the cry/text to actually start battle; sampling hJoyPressed/hJoyHeld
    // makes A2 visible even when the overlay misses the physical release/press.
    if title == BLUE_JP_TITLE_ID && bits == Button::A as u32 {
        return unsafe { bindings::host_blue_game_a_edge() } != 0;
    }

    unsafe { bindings::host_is_just_pressed(bits) } != 0
}

pub fn is_pressing(io_bits: impl Into<u32>) -> bool {
    let current_keys = unsafe { bindings::get_current_keys() };
    (current_keys & io_bits.into()) != 0
}

pub fn blue_game_joy() -> (u8, u8) {
    (
        unsafe { bindings::host_blue_game_joy_pressed() } as u8,
        unsafe { bindings::host_blue_game_joy_held() } as u8,
    )
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct BlueFixedState {
    pub remaining: u8,
    pub pending: bool,
    pub wait_a_release: bool,
    pub physical_a: bool,
    pub paused: bool,
    pub error: u8,
}

pub fn blue_fixed_run_id() -> u32 {
    unsafe { bindings::host_blue_fixed_run_id() }
}

pub fn blue_fixed_state() -> BlueFixedState {
    let raw = unsafe { bindings::host_blue_fixed_state() };
    BlueFixedState {
        remaining: (raw & 0x7) as u8,
        pending: raw & (1 << 3) != 0,
        wait_a_release: raw & (1 << 4) != 0,
        physical_a: raw & (1 << 5) != 0,
        paused: raw & (1 << 6) != 0,
        error: ((raw >> 8) & 0xF) as u8,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn blue_state_layout_is_stable() {
        let raw = 2 | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6) | (3 << 8);
        let s = BlueFixedState {
            remaining: (raw & 0x7) as u8,
            pending: raw & (1 << 3) != 0,
            wait_a_release: raw & (1 << 4) != 0,
            physical_a: raw & (1 << 5) != 0,
            paused: raw & (1 << 6) != 0,
            error: ((raw >> 8) & 0xF) as u8,
        };
        assert_eq!(s.remaining, 2);
        assert!(s.pending && s.wait_a_release && s.physical_a && s.paused);
        assert_eq!(s.error, 3);
    }
}
