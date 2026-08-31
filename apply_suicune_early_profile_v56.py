#!/usr/bin/env python3
from pathlib import Path

main_path = Path("3gx/sources/main.c")
trace_path = Path("reader_core/src/crystal/trace.rs")

m = main_path.read_text()
t = trace_path.read_text()


def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, got {n}")
    return src.replace(old, new, 1)


# -------------------------------------------------------------------------
# Suicune Early Control Lab v5.6
#
# v5.5 proved that the rel26 -> rel27 transition can be controlled directly,
# but manual E-slot selection is error-prone because the Rust overlay does not
# redraw while the game is paused. v5.6 removes the manual selector entirely.
# Every fresh Y+X arm automatically rotates through three controlled profiles:
#
#   Profile A = E07 ON
#   Profile B = E08 ON
#   Profile C = E09 ON
#
# S00/P00 remain fixed. The selected profile is latched at arm time and stays
# unchanged for the entire trial. After C, the next arm returns to A.
# -------------------------------------------------------------------------

m = rep(
    m,
    "static u32 suicune_early_phase_slot = 0;\nstatic u32 suicune_early_slot_used = 0;",
    "static u32 suicune_early_phase_slot = 0;\nstatic u32 suicune_early_profile_next = 0;\nstatic u32 suicune_early_slot_used = 0;",
    "add v56 profile counter",
)

m = rep(
    m,
    '''static void suicune_early_lab_reset(void)
{
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_gate_pending = false;''',
    '''static void suicune_early_lab_reset(void)
{
    static const u32 profile_slots[3] = {7, 8, 9};

    // Latch exactly one profile for this Y+X arm. Early control is always ON
    // in v5.6; there is no pause-screen UI state to keep in sync.
    suicune_early_control_enabled = true;
    suicune_early_phase_slot = profile_slots[suicune_early_profile_next % 3];
    suicune_early_profile_next = (suicune_early_profile_next + 1) % 3;
    suicune_early_slot_used = suicune_early_phase_slot;
    suicune_early_gate_pending = false;''',
    "rotate v56 profile on arm",
)

m = rep(
    m,
    '''            // v5.5 selector: S00/P00 are fixed; D-pad controls only the
            // rel26->27 Early gate. Right/Left +/-1, Down opposite half-cycle,
            // Up toggles Early control ON/OFF for a natural baseline trial.
            suicune_phase_slot = 0;
            suicune_start_phase_slot = 0;
            if (just_pressed & KEY_DRIGHT)
                suicune_early_phase_slot = (suicune_early_phase_slot + 1) & 0x0f;
            if (just_pressed & KEY_DLEFT)
                suicune_early_phase_slot = (suicune_early_phase_slot + 15) & 0x0f;
            if (just_pressed & KEY_DDOWN)
                suicune_early_phase_slot ^= 8;
            if (just_pressed & KEY_DUP)
                suicune_early_control_enabled = !suicune_early_control_enabled;''',
    '''            // v5.6: S00/P00 remain fixed. E is selected automatically
            // when Y+X arms the trial (A=E07, B=E08, C=E09). D-pad input is
            // deliberately ignored here so pause-screen redraw timing cannot
            // create a hidden configuration mismatch.
            suicune_phase_slot = 0;
            suicune_start_phase_slot = 0;''',
    "remove manual v55 early selector",
)

# CSV: add a compact PROFILE row, promote the lab version to V56, and include
# the profile letter in the structured EARLY row. The slot remains recorded as
# the ground-truth actuator value even if a future build changes the mapping.
t = rep(
    t,
    '''        let eerr = em.actual as i128 - em.target as i128;
        let _ = write!(line,
            "early_lab,version,enabled,selected_slot,used_slot,requests,repeat_count,gate_seen,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks,pre_valid,pre_advance,pre_state,pre_ap4,pre_sp4,pre_asub,pre_ssub,post1_valid,post1_advance,post1_state,post1_ap4,post1_sp4,j_a,j_s,post2_valid,post2_advance,post2_state,post2_ap4,post2_sp4,next_resid_a,next_resid_s\\n"''',
    '''        let eerr = em.actual as i128 - em.target as i128;
        let profile = match em.selected_slot {
            7 => "A",
            8 => "B",
            9 => "C",
            _ => "?",
        };
        let _ = write!(line, "PROFILE,{},E{:02},ON\\n", profile, em.selected_slot);
        pnp::trace_file_write(line.as_bytes());
        line.clear();
        let _ = write!(line,
            "early_lab,version,profile,enabled,selected_slot,used_slot,requests,repeat_count,gate_seen,period_ticks,anchor_tick,target_tick,actual_tick,error_ticks,pre_valid,pre_advance,pre_state,pre_ap4,pre_sp4,pre_asub,pre_ssub,post1_valid,post1_advance,post1_state,post1_ap4,post1_sp4,j_a,j_s,post2_valid,post2_advance,post2_state,post2_ap4,post2_sp4,next_resid_a,next_resid_s\\n"''',
    "add v56 profile csv header",
)

t = rep(
    t,
    '            "EARLY,V55,',
    '            "EARLY,V56,{},',
    "promote early row to v56",
)

t = rep(
    t,
    '''            em.enabled as u8, em.selected_slot, em.used_slot, em.requests,''',
    '''            profile, em.enabled as u8, em.selected_slot, em.used_slot, em.requests,''',
    "write v56 profile in early row",
)

# On-screen status is diagnostic only. There are no controls to operate while
# paused; this simply makes the currently latched profile visible once drawing
# resumes.
t = rep(
    t,
    '''        let em = pnp::early_control_metrics();
        pnp::println!(
            "Lab E{:02} {} C{} G{}",
            em.selected_slot,
            if em.enabled { "ON" } else { "OFF" },
            self.early_rel26_count,
            self.early_gate_seen as u8
        );''',
    '''        let em = pnp::early_control_metrics();
        let profile = match em.selected_slot {
            7 => "A",
            8 => "B",
            9 => "C",
            _ => "?",
        };
        pnp::println!(
            "Lab {} E{:02} C{} G{}",
            profile,
            em.selected_slot,
            self.early_rel26_count,
            self.early_gate_seen as u8
        );''',
    "draw v56 profile status",
)

main_path.write_text(m)
trace_path.write_text(t)
print("Applied Suicune Early Control Lab v5.6 automatic profiles")
