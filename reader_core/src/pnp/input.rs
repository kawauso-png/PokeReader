use super::bindings;
use core::{
    cmp::PartialEq,
    ops::{BitAnd, BitOr},
};
use num_enum::IntoPrimitive;

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

    fn bitand(self, rhs: Button) -> Self::Output {
        self & (rhs as u32)
    }
}

impl BitOr for Button {
    type Output = u32;

    fn bitor(self, rhs: Self) -> Self::Output {
        (self as u32) | (rhs as u32)
    }
}

/// Check if buttons were just pressed.
/// Convenient for one time checks.
///
/// # Examples
/// ```
/// use pnp::{Button, is_just_pressed};
///
/// if is_just_pressed(Button::Dup | Button::Ddown) {
///   // Do something
/// }
/// ```
pub fn is_just_pressed(io_bits: impl Into<u32>) -> bool {
    let is_pressed = unsafe { bindings::host_is_just_pressed(io_bits.into()) };
    is_pressed != 0
}

pub fn is_pressing(io_bits: impl Into<u32>) -> bool {
    let current_keys = unsafe { bindings::get_current_keys() };
    (current_keys & io_bits.into()) != 0
}

/// State of the Fixed A Frame feature, packed by the plugin's C side.
pub struct FixedAFrame {
    pub frames: u8,
    pub last_run: u8,
    pub armed: bool,
    pub running: bool,
    pub pending: bool,
    pub physical_a: bool,
    pub physical_up: bool,
}

/// Read the Fixed A Frame state.
pub fn fixed_a_frame() -> FixedAFrame {
    let bits = unsafe { bindings::host_fixed_state() };
    FixedAFrame {
        frames: (bits & 0xff) as u8,
        last_run: ((bits >> 8) & 0xff) as u8,
        armed: (bits & (1 << 16)) != 0,
        running: (bits & (1 << 17)) != 0,
        physical_a: (bits & (1 << 18)) != 0,
        physical_up: (bits & (1 << 19)) != 0,
        pending: (bits & (1 << 20)) != 0,
    }
}

/// Increments every time a Fixed A Frame run starts. Lets other code arm
/// itself off the run without needing its own hotkey.
pub fn fixed_run_id() -> u32 {
    unsafe { bindings::host_fixed_run_id() }
}

/// Celebi trace arming, toggled from the pause loop with Y + START.
/// Returns the toggle counter and whether the trace is currently armed.
pub fn trace_request() -> (u32, bool) {
    let bits = unsafe { bindings::host_trace_request() };
    (bits & 0x7fff_ffff, (bits & 0x8000_0000) != 0)
}

/// Opens a CSV under /luma/plugins/pokereader/traces/. Returns false if the
/// plugin is not allowed to touch the SD card.
pub fn trace_file_open(index: u32) -> bool {
    unsafe { bindings::host_trace_file_open(index) != 0 }
}

pub fn trace_file_write(data: &[u8]) -> u32 {
    unsafe { bindings::host_trace_file_write(data.as_ptr(), data.len() as u32) }
}

pub fn trace_file_close() {
    unsafe { bindings::host_trace_file_close() }
}

/// Ask the C host to enter its existing freeze loop at the next screen hook.
pub fn request_pause() {
    unsafe { bindings::host_request_pause() }
}

/// Raw 3DS key bitfield for the current frame.
pub fn current_keys() -> u32 {
    unsafe { bindings::get_current_keys() }
}

/// Raw 3DS Result code from the last failed trace save.
pub fn trace_last_error() -> u32 {
    unsafe { bindings::host_trace_last_error() }
}

/// Stop and save counters, bumped from the pause loop with Y + SELECT and
/// Y + A. Returns (stop_requests, save_requests).
pub fn trace_cmds() -> (u32, u32) {
    let bits = unsafe { bindings::host_trace_cmds() };
    (bits & 0xffff, (bits >> 16) & 0xffff)
}

/// File number the last successful save actually used.
pub fn trace_written_slot() -> u32 {
    unsafe { bindings::host_trace_written_slot() }
}
