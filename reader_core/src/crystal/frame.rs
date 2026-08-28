use super::{
    draw::{draw_header, draw_pkx, draw_research, draw_rng},
    hook::{measured_div, reset_rng_advance},
    reader::Gen2Reader,
};
use crate::{
    pnp,
    utils::{
        help_menu::HelpMenu,
        menu::{Menu, MenuOption},
        sub_menu::SubMenu,
        ShowView,
    },
};
use once_cell::unsync::Lazy;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CrystalView {
    MainMenu,
    Rng,
    Party,
    Wild,
    Egg,
    Research,
    Memory,
    Trace,
    HelpMenu,
}

struct PersistedState {
    frame: usize,
    show_view: ShowView,
    view: CrystalView,
    main_menu: Menu<CrystalView>,
    party_menu: SubMenu,
    help_menu: HelpMenu,
    mem_view: super::memview::MemView,
    trace: super::trace::Trace,
}

const MENU: &[MenuOption<CrystalView>] = &[
    MenuOption::new(CrystalView::Rng, "RNG"),
    MenuOption::new(CrystalView::Party, "Party"),
    MenuOption::new(CrystalView::Wild, "Wild"),
    MenuOption::new(CrystalView::Egg, "Egg"),
    MenuOption::new(CrystalView::Research, "Research"),
    MenuOption::new(CrystalView::Memory, "Memory"),
    MenuOption::new(CrystalView::Trace, "Trace"),
    MenuOption::new(CrystalView::HelpMenu, "Help"),
];

unsafe fn get_state() -> &'static mut PersistedState {
    static mut STATE: Lazy<PersistedState> = Lazy::new(|| PersistedState {
        frame: 0,
        show_view: ShowView::default(),
        view: CrystalView::MainMenu,
        party_menu: SubMenu::new(1, 6),
        help_menu: HelpMenu::default(),
        mem_view: super::memview::MemView::default(),
        trace: super::trace::Trace::default(),
        main_menu: Menu::new(MENU),
    });
    Lazy::force_mut(&mut STATE)
}


/// Invoked directly from the C pause loop by Y+X.  This is intentionally not
/// deferred to run_frame(): deferring would lose the exact Target state and
/// only see Target+1 after resume.
pub fn arm_suicune_probe() {
    let reader = Gen2Reader::crystal();
    let state = unsafe { get_state() };
    state.trace.arm_suicune_probe(&reader);
}

pub fn run_frame() {
    pnp::set_print_max_len(22);

    let reader = Gen2Reader::crystal();

    // This is safe as long as this is guaranteed to run single threaded.
    // A lock hinders performance too much on a 3ds.
    let state = unsafe { get_state() };

    state.frame = match (measured_div(), reader.rng_state()) {
        (0x0101, 0x01ff) => {
            reset_rng_advance();
            1
        }
        _ => state.frame.wrapping_add(1),
    };

    state.trace.record(&reader);

    if !state.show_view.check() {
        return;
    }

    let is_locked = state.main_menu.update_lock();
    state.view = state.main_menu.next_view(CrystalView::MainMenu, state.view);
    draw_header(CrystalView::MainMenu, state.view, is_locked);

    match state.view {
        CrystalView::Rng => {
            draw_rng(&reader);
            state.trace.draw_rng_status();
            let (status, start, len) = state.trace.status_line();
            pnp::println!("Trace {} {} f{}", status, start, len);
            let (save, code) = state.trace.save_status();
            pnp::println!("Save {} {:08X}", save, code);
        }
        CrystalView::Wild => draw_pkx(&reader.wild()),
        CrystalView::Party => {
            let slot = state.party_menu.update_and_draw(is_locked);
            draw_pkx(&reader.party((slot - 1) as u8));
        }
        CrystalView::Egg => draw_pkx(&reader.egg()),
        CrystalView::Research => draw_research(&reader, state.frame),
        CrystalView::Memory => {
            state.mem_view.update_and_draw(is_locked);
            if let Some(addr) = state.mem_view.watch_request.take() {
                state.trace.set_watch_addr(addr);
            }
        }
        CrystalView::Trace => state.trace.draw(&reader, is_locked),
        CrystalView::HelpMenu => state.help_menu.update_and_draw(is_locked),
        CrystalView::MainMenu => {
            state.main_menu.update_view();
            state.main_menu.draw();
        }
    }
}
