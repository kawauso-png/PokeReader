#!/usr/bin/env python3
from pathlib import Path
H=Path('reader_core/src/crystal/hook.rs').read_text()
T=Path('reader_core/src/crystal/trace.rs').read_text()
M=Path('3gx/sources/main.c').read_text()

def need(x,m,label):
    if m not in x: raise SystemExit('v731 missing '+label+': '+m)
def forbid(x,m,label):
    if m in x: raise SystemExit('v731 forbidden '+label+': '+m)

# Physical execution path must remain the already-proven UP+B Exact2F path.
need(M,'(just_pressed & KEY_B) && (held & KEY_DUP) && !(held & KEY_Y)','UP+B trigger')
need(M,'if ((held & (KEY_B | KEY_Y | KEY_X | KEY_L | KEY_R)) == 0)','B-release gate')
need(M,'suicune_auto_resume_pending && !(held & KEY_DUP)','UP hold safety')
need(T,'S731 TEST UP+B','UP+B UI')

# Detector is evidence-only in the hook: paired A/S gap, no reset from A alone.
need(H,'static mut VC_DIV_DISCONT_EPOCH: u32 = 0;','reset epoch')
need(H,'d != 0x12 && d != 0x13','normal DIV whitelist')
need(H,'if old_advance < 64 { return false; }','startup false-positive guard')
need(H,'VC_DIV_A_ADV == now_advance','same-VBlank A/S pairing')
need(H,'VC_DIV_DISCONT_EPOCH = VC_DIV_DISCONT_EPOCH.wrapping_add(1);','paired event')
a=H.index('if RNG_DIV_READ_1.contains(&pc)'); s=H.index('if RNG_DIV_READ_2.contains(&pc)')
forbid(H[a:s],'reset_vc_session_observers();','never wipe in A hook')

# Comprehensive per-boot observer wipe.
rs=H.index('pub fn reset_vc_session_observers()'); re=H.index('pub fn rng_advance()',rs); r=H[rs:re]
for m in [
    'RNG_ADVANCE = 0','ADIV = 0','SDIV = 0','CYCLE_COUNTER = 0',
    'ADD_DIV_TRACKER = DivTracker::new()','SUB_DIV_TRACKER = DivTracker::new()',
    'PRE_VBLANK_RING = PreVBlankRing::EMPTY','LAST_VBLANK_CONTEXT = VBlankContextSnapshot::EMPTY',
    'VBLANK_CONTEXT_CAPTURE_ENABLED = true','V53_HITS = 0','V53_CPU_CTX = [0; VBLANK_CTX_LEN]',
    'CALL_WRITE = 0','CALL_COUNT = 0','CALL_LOGGING = false',
    'DEEP_WRITE = 0','DEEP_COUNT = 0','DEEP_LOGGING = false','ENDPOINT_FAST_TAIL = false',
    'diff_probe_clear();'
]: need(r,m,'observer wipe '+m)
forbid(r,'VC_DIV_DISCONT_EPOCH = 0','epoch must survive wipe')

# Trace consumes reset only outside active encounter execution.
need(T,'fn handle_vc_soft_reset','Trace reset consumer')
h=T[T.index('fn handle_vc_soft_reset'):T.index('pub fn record',T.index('fn handle_vc_soft_reset'))]
need(h,'let encounter_executing = self.probe_active || self.practical_active;','encounter guard')
need(h,'if has_session && !encounter_executing','safe reset context')
need(h,'let mut fresh = Self::default();','full Trace reset from Default')
need(h,'fresh.save_index = keep_save_index;','preserve file slot')
need(h,'fresh.watch_addr = keep_watch_addr;','preserve watch')
need(h,'fresh.practical_search_enabled = true;','RESET WAIT UI gate')
need(h,'fresh.practical_live_scan = false;','no title-screen scan')
need(h,'self.sync_host_command_ids();','queued host command sync')
need(h,'pnp::request_resume();','leave stale pause')

# Auto rearm requires loaded-save signature plus data proven to have been
# rebuilt after reset. It must NOT depend on matching a known PRE prototype,
# otherwise v7.3 would reintroduce the exact P0/X0 coverage dead-zone it fixed.
need(T,'gb_mem::read_u8(0xdc9d)','JP party count gate')
need(T,'gb_mem::read_u8(0xdc9e)','JP first species gate')
need(h,'reader.trainer_id() == self.soft_reset_expected_tid','same save TID')
need(h,'self.soft_reset_saw_unloaded || play_moved','boot/load proof')
need(h,'let rr = latest_pre_vblank_ring();','fresh ring read')
need(h,'rn == PRE_VBLANK_RING_LEN','full fresh ring')
need(h,'rng_advance().wrapping_sub(last_adv) <= 1','current ring')
need(h,'add_div_tracker().index().is_some()','fresh A index')
need(h,'sub_div_tracker().index().is_some()','fresh S index')
forbid(h,'let pre_fresh = self.live_pre_cell().is_some();','PRE-class-dependent rearm')
need(h,'if self.soft_reset_loaded_streak < 8','stable loaded streak')
need(h,'self.search_practical_targets(reader);','automatic fresh SCAN')

# Reset handling is the first action in record(), before stale host requests or
# the GlobalBeam monitor can observe old counters.
record=T[T.index('pub fn record(&mut self, reader: &Gen2Reader) {'):]
first=record.find('if self.handle_vc_soft_reset(reader)')
arm=record.find('let (arm_id, armed) = pnp::trace_request()')
if first<0 or arm<0 or first>arm: raise SystemExit('v731 reset handler not first in record')

# v7.3 GlobalBeam architecture and hard guards are still present.
for m in ['fn practical_wait_monitor','evaluate_empirical_id','fn rebind_shiny_post_v730','practical_expected716_state','practical_expected717_state','GLOBALBEAM,V731']:
    need(T,m,'GlobalBeam invariant '+m)
need(T,'S731 RESET WAIT','reset wait UI')
need(T,'SOFTRESET,V731','reset telemetry')
forbid(T,'S730 ','stale UI')

print('v7.3.1 AUDIT PASS: paired DIV evidence only; encounter stalls cannot trigger wipe; full observer/Trace reset; loaded-save + fresh-ring/index rearm independent of PRE coverage; automatic fresh SCAN; UP+B and 716/717 guards preserved')
