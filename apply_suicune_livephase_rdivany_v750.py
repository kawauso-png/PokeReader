#!/usr/bin/env python3
from pathlib import Path

H=Path('reader_core/src/crystal/hook.rs')
T=Path('reader_core/src/crystal/trace.rs')
h=H.read_text(); t=T.read_text()

def need(c,msg):
    if not c: raise SystemExit('v750 '+msg)
def rep(s,old,new,msg):
    n=s.count(old)
    if n!=1: raise SystemExit(f'v750 {msg}: expected 1 got {n}')
    return s.replace(old,new,1)

# ---------------------------------------------------------------------------
# A. Broad non-VBlank rDIV read ring. This intentionally does NOT guess the
# final Random PCs. It records every FF04 read except the normal VBlank A/S
# sites, while the lightweight event-phase logger is active. Last 128 survive.
# ---------------------------------------------------------------------------
if 'pub struct RDivAnyEntryV750' not in h:
    anchor='pub const RANDOM_PHASE_LOG_LEN_V747: usize = 256;'
    need(anchor in h,'random phase anchor missing')
    block=r'''
pub const RDIV_ANY_LEN_V750: usize = 128;
#[derive(Clone,Copy,Default)]
pub struct RDivAnyEntryV750 {
    pub index:u32,
    pub advance:u32,
    pub pc:u16,
    pub div:u8,
    pub mcycle:u8,
    pub host_tick:u64,
    pub state:u16,
    pub add:u8,
    pub sub:u8,
}
impl RDivAnyEntryV750 {
    const EMPTY:Self=Self{index:0,advance:0,pc:0,div:0,mcycle:0,host_tick:0,state:0,add:0,sub:0};
}
static mut RDIV_ANY_LOG_V750:[RDivAnyEntryV750;RDIV_ANY_LEN_V750]=[RDivAnyEntryV750::EMPTY;RDIV_ANY_LEN_V750];
static mut RDIV_ANY_WRITE_V750:usize=0;
static mut RDIV_ANY_COUNT_V750:u32=0;

pub fn rdiv_any_count_v750()->u32{unsafe{RDIV_ANY_COUNT_V750}}
pub fn rdiv_any_entry_v750(index:usize)->RDivAnyEntryV750{
    unsafe{
        let total=RDIV_ANY_COUNT_V750 as usize;
        let shown=total.min(RDIV_ANY_LEN_V750);
        if index>=shown{return RDivAnyEntryV750::EMPTY}
        let start=if total>RDIV_ANY_LEN_V750{RDIV_ANY_WRITE_V750}else{0};
        RDIV_ANY_LOG_V750[(start+index)%RDIV_ANY_LEN_V750]
    }
}
fn capture_rdiv_any_v750(reader:&Gen2Reader,pc:u16,host_tick:u64,mcycle:u8){
    unsafe{
        if !RANDOM_PHASE_LOGGING_V748{return;}
        if matches!(pc,0x02b5|0x02b6|0x02bd|0x02be){return;}
        let e=RDivAnyEntryV750{
            index:RDIV_ANY_COUNT_V750,
            advance:rng_advance(),pc,div:reader.div(),mcycle,host_tick,
            state:reader.rng_state(),add:reader.rng_add(),sub:reader.rng_sub(),
        };
        RDIV_ANY_LOG_V750[RDIV_ANY_WRITE_V750]=e;
        RDIV_ANY_WRITE_V750=(RDIV_ANY_WRITE_V750+1)%RDIV_ANY_LEN_V750;
        RDIV_ANY_COUNT_V750=RDIV_ANY_COUNT_V750.wrapping_add(1);
    }
}
'''
    h=h.replace(anchor,block+'\n'+anchor,1)

# Reset broad ring with each Suicune probe start/clear.
if 'RDIV_ANY_COUNT_V750=0;' not in h[h.find('pub fn deep_log_start()'):h.find('pub fn deep_log_stop()')]:
    old='''        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;'''
    new='''        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;\n        RDIV_ANY_WRITE_V750=0;\n        RDIV_ANY_COUNT_V750=0;'''
    h=rep(h,old,new,'deep start broad reset')
# deep_log_clear has same pair; patch second occurrence now.
if h.count('RDIV_ANY_COUNT_V750=0;')<2:
    pos=h.find('pub fn deep_log_clear()')
    need(pos>=0,'deep clear missing')
    tail=h[pos:]
    old='''        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;'''
    need(old in tail,'deep clear reset anchor missing')
    tail=tail.replace(old,'''        RANDOM_PHASE_WRITE_V747=0;\n        RANDOM_PHASE_COUNT_V747=0;\n        RDIV_ANY_WRITE_V750=0;\n        RDIV_ANY_COUNT_V750=0;''',1)
    h=h[:pos]+tail

if 'capture_rdiv_any_v750(&reader, pc, host_tick, mcycle);' not in h:
    anchor='    capture_random_phase_v747(&reader, pc, host_tick, mcycle);'
    need(anchor in h,'random phase call missing')
    h=h.replace(anchor,'    capture_rdiv_any_v750(&reader, pc, host_tick, mcycle);\n'+anchor,1)

# ---------------------------------------------------------------------------
# B. Direct live DIV per top hook. This is a read-only Gen2Reader FF04 sample.
# Combined with v748 live F604 mcycle it yields a direct 14-bit live phase.
# ---------------------------------------------------------------------------
if 'pub hook_live_div_v750: u8,' not in t:
    anchor='    pub hook_live_mcycle_v748: u8,\n'
    need(anchor in t,'TraceEntry live mcycle field missing')
    t=t.replace(anchor,anchor+'    pub hook_live_div_v750: u8,\n',1)
    anchor='        hook_live_mcycle_v748: 0,\n'
    need(anchor in t,'TraceEntry empty live mcycle missing')
    t=t.replace(anchor,anchor+'        hook_live_div_v750: 0,\n',1)

if 'let hook_live_div_v750=reader.div();' not in t:
    anchor='        let hook_live_mcycle_v748=host_frame_live_mcycle_v748();\n'
    need(anchor in t,'record live mcycle anchor missing')
    t=t.replace(anchor,anchor+'        let hook_live_div_v750=reader.div();\n',1)
    anchor='            hook_live_mcycle_v748,\n'
    need(anchor in t,'TraceEntry init live mcycle missing')
    t=t.replace(anchor,anchor+'            hook_live_div_v750,\n',1)

# Trigger live DIV snapshot.
if 'nptest_trigger_live_div_v750: u8,' not in t:
    anchor='    nptest_trigger_live_mcycle_v748: u8,\n'
    need(anchor in t,'nptest mcycle field missing')
    t=t.replace(anchor,anchor+'    nptest_trigger_live_div_v750: u8,\n',1)
    anchor='            nptest_trigger_live_mcycle_v748: 0,\n'
    need(anchor in t,'nptest default mcycle missing')
    t=t.replace(anchor,anchor+'            nptest_trigger_live_div_v750: 0,\n',1)
    anchor='        self.nptest_trigger_live_mcycle_v748=0;\n'
    need(anchor in t,'nptest reset mcycle missing')
    t=t.replace(anchor,anchor+'        self.nptest_trigger_live_div_v750=0;\n',1)
    anchor='                    self.nptest_trigger_live_mcycle_v748=host_frame_live_mcycle_v748();\n'
    need(anchor in t,'nptest trigger mcycle assignment missing')
    t=t.replace(anchor,anchor+'                    self.nptest_trigger_live_div_v750=reader.div();\n',1)

# Import broad-ring helpers.
if 'rdiv_any_count_v750' not in t.split('};',1)[0]:
    anchor='    host_frame_live_mcycle_v748, host_frame_metrics_v747, random_phase_count_v747, random_phase_entry_v747, random_phase_stop_v748,\n'
    need(anchor in t,'trace hook import line missing')
    t=t.replace(anchor,'    host_frame_live_mcycle_v748, host_frame_metrics_v747, random_phase_count_v747, random_phase_entry_v747, random_phase_stop_v748, rdiv_any_count_v750, rdiv_any_entry_v750,\n',1)

# ---------------------------------------------------------------------------
# C. Append-only V750 sections. Do not alter legacy/V748 sections.
# ---------------------------------------------------------------------------
if 'RDIVANY,V750' not in t:
    close='        pnp::trace_file_close();'
    need(t.count(close)==1,'trace close not unique')
    sec=r'''        line.clear();
        let _=write!(line,"\nrdivany,version,index,advance,pc,div,mcycle,host_tick,state,add,sub\n");
        pnp::trace_file_write(line.as_bytes());
        let rac=rdiv_any_count_v750() as usize;
        for i in 0..rac.min(super::hook::RDIV_ANY_LEN_V750){
            let e=rdiv_any_entry_v750(i);
            line.clear();
            let _=write!(line,"RDIVANY,V750,{},{},{:04X},{:02X},{:02X},{},{:04X},{:02X},{:02X}\n",
                e.index,e.advance,e.pc,e.div,e.mcycle,e.host_tick,e.state,e.add,e.sub);
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let _=write!(line,"frame3,version,index,advance,hook_frame_index,hook_frame_mod16,hook_tick,live_div,live_mcycle,live_phase\n");
        pnp::trace_file_write(line.as_bytes());
        for i in 0..self.len{
            let e=&self.entries[i];
            let phase=(((e.hook_live_div_v750 as u16)<<6)|((e.hook_live_mcycle_v748 as u16)&0x3f))&0x3fff;
            line.clear();
            let _=write!(line,"FRAME3,V750,{},{},{},{},{},{:02X},{:02X},{:04X}\n",i,e.advance,
                e.hook_frame_index_v747,e.hook_frame_index_v747&15,e.hook_tick_v747,
                e.hook_live_div_v750,e.hook_live_mcycle_v748,phase);
            pnp::trace_file_write(line.as_bytes());
        }

        line.clear();
        let trig_phase=(((self.nptest_trigger_live_div_v750 as u16)<<6)|((self.nptest_trigger_live_mcycle_v748 as u16)&0x3f))&0x3fff;
        let _=write!(line,"npjt3,version,trigger_advance,hook_index,hook_mod16,hook_tick,live_div,live_mcycle,live_phase\nNPJT3,V750,{},{},{},{},{:02X},{:02X},{:04X}\n",
            self.nptest_trigger_advance,self.nptest_trigger_hook_index_v748,self.nptest_trigger_hook_index_v748&15,
            self.nptest_trigger_hook_tick_v748,self.nptest_trigger_live_div_v750,self.nptest_trigger_live_mcycle_v748,trig_phase);
        pnp::trace_file_write(line.as_bytes());

'''
    t=t.replace(close,sec+close,1)

H.write_text(h); T.write_text(t)
print('Applied Suicune v7.5.0: direct live DIV/F604 phase and broad non-VBlank rDIV PC telemetry')
