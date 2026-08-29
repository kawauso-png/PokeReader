use crate::pnp;
use alloc::{format, string::String};
use num_enum::TryFromPrimitive;

#[derive(Clone, Copy, Debug, PartialEq, Eq, TryFromPrimitive)]
#[repr(u64)]
pub enum LoadedTitle {
    X = 0x0004000000055D00,
    Y = 0x0004000000055E00,
    Or = 0x000400000011C400,
    As = 0x000400000011C500,
    S = 0x0004000000164800,
    M = 0x0004000000175E00,
    Us = 0x00040000001B5000,
    Um = 0x00040000001B5100,
    Transporter = 0x00040000000C9C00,
    BlueJp = 0x0004000000170E00,
    CrystalEn = 0x0004000000172800,
    CrystalDe = 0x0004000000172B00,
    CrystalFr = 0x0004000000172E00,
    CrystalEs = 0x0004000000173100,
    CrystalIt = 0x0004000000173400,
    CrystalJp = 0x0004000000172500,
}

#[derive(Debug, Clone)]
pub enum TitleError {
    InvalidTitle,
    InvalidUpdate {
        remaster_version: u16,
        debug_info: Option<String>,
        is_citra: bool,
    },
}

static mut LOADED: bool = false;
static mut LOAD_RESULT: Result<LoadedTitle, TitleError> = Err(TitleError::InvalidTitle);

fn check_citra_title_version(addr: u32, expected: &'static [u8; 16], version: u16) -> UpdateInfo {
    let version_bytes = pnp::read_array::<16>(addr);
    let version = match &version_bytes == expected {
        true => version,
        false => 0,
    };
    UpdateInfo {
        version,
        debug_info: Some(
            version_bytes
                .iter()
                .map(|byte| format!("{:02x}", byte))
                .collect::<String>(),
        ),
    }
}

struct UpdateInfo {
    version: u16,
    debug_info: Option<String>,
}

fn get_citra_title_version(title: LoadedTitle) -> UpdateInfo {
    match title {
        LoadedTitle::S => check_citra_title_version(0x3d3a90, b"8QjtffIMWFhiFpTz", 2),
        LoadedTitle::M => check_citra_title_version(0x3d3a90, b"7mXz0DXR4b4CdD8r", 2),
        LoadedTitle::Us => check_citra_title_version(0x3e5884, b"fnCAH3KrGIl9dgSd", 2),
        LoadedTitle::Um => check_citra_title_version(0x3e5888, b"b3Gq6LF6EqE1bvKy", 2),
        LoadedTitle::Or => check_citra_title_version(0x1086bc, b"cRFY0WFHNjPh44If", 7),
        LoadedTitle::As => check_citra_title_version(0x1086bc, b"guBwm9TlQvYvncKn", 7),
        LoadedTitle::X => check_citra_title_version(0x10869c, b"h0VRqB2YEgq39zvO", 5),
        LoadedTitle::Y => check_citra_title_version(0x10869c, b"Slv7vHlUOfqrKMpz", 5),
        LoadedTitle::Transporter => UpdateInfo {
            version: 5,
            debug_info: None,
        },
        LoadedTitle::BlueJp => UpdateInfo {
            version: 1056,
            debug_info: None,
        },
        LoadedTitle::CrystalEn
        | LoadedTitle::CrystalDe
        | LoadedTitle::CrystalFr
        | LoadedTitle::CrystalEs
        | LoadedTitle::CrystalIt
        | LoadedTitle::CrystalJp => UpdateInfo {
            version: 0,
            debug_info: None,
        },
    }
}

fn get_update_version(title: LoadedTitle) -> UpdateInfo {
    if pnp::is_citra() {
        return get_citra_title_version(title);
    }

    UpdateInfo {
        version: pnp::update_version(),
        debug_info: None,
    }
}

pub fn loaded_title() -> &'static Result<LoadedTitle, TitleError> {
    unsafe {
        if LOADED {
            return &LOAD_RESULT;
        }

        LOADED = true;

        let title = match pnp::title_id().try_into() {
            Ok(title) => title,
            Err(_) => {
                LOAD_RESULT = Err(TitleError::InvalidTitle);
                return &LOAD_RESULT;
            }
        };

        let update_info = get_update_version(title);
        LOAD_RESULT = match (title, update_info.version) {
            (LoadedTitle::S, 2)
            | (LoadedTitle::M, 2)
            | (LoadedTitle::Us, 2)
            | (LoadedTitle::Um, 2)
            | (LoadedTitle::Or, 7)
            | (LoadedTitle::As, 7)
            | (LoadedTitle::X, 5)
            | (LoadedTitle::Y, 5)
            | (LoadedTitle::Transporter, 5)
            // Japanese VC Blue on the user's real 3DS reports remaster/update
            // version 1. Keep 0 for older hardware-path builds and 1056 for the
            // Citra compatibility path already used by this project.
            | (LoadedTitle::BlueJp, 0)
            | (LoadedTitle::BlueJp, 1)
            | (LoadedTitle::BlueJp, 1056)
            | (LoadedTitle::CrystalEn, 0)
            | (LoadedTitle::CrystalDe, 0)
            | (LoadedTitle::CrystalFr, 0)
            | (LoadedTitle::CrystalEs, 0)
            | (LoadedTitle::CrystalIt, 0)
            | (LoadedTitle::CrystalJp, 0) => Ok(title),
            (_, remaster_version) => Err(TitleError::InvalidUpdate {
                remaster_version,
                debug_info: update_info.debug_info,
                is_citra: pnp::is_citra(),
            }),
        };

        &LOAD_RESULT
    }
}
