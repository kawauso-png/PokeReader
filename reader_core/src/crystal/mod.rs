mod boottrace;
mod draw;
mod frame;
mod game_lib;
mod hook;
mod memview;
mod trace;
mod pk2;
mod reader;

pub use draw::CRYSTAL_CYAN;
pub use frame::{arm_suicune_probe, run_frame};

/// Install the normal Crystal hooks, then start the existing lightweight rDIV
/// call logger before the VC is allowed to run. This gives the diagnostic Boot
/// page a continuous call stream from the earliest hooked RNG activity onward.
pub fn init_crystal() {
    hook::init_crystal();
    hook::call_log_start();
}
