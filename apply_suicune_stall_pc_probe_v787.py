#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()


def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v787 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.8.7 is observation-only.  The existing v7.8.6 input/RNG/DIV path is
# untouched.  We sample the emulator's current GB PC and live rDIV byte only
# during the first 40 relative advances of a Suicune probe.  This brackets the
# fixed ~13-present stop around rel26/27 while adding only a few read-only host
# memory accesses and 4 bytes per TraceEntry.

t = rep(
    t,
    '''    pub atick: u64,\n    pub stick: u64,\n}''',
    '''    pub atick: u64,\n    pub stick: u64,\n    /// v7.8.7: current emulator execution point sampled from the top-screen\n    /// present hook.  0xFFFF/0xFF means outside the early probe window.\n    pub sample_pc: u16,\n    pub sample_live_div: u8,\n}''',
    'TraceEntry fields',
)

t = rep(
    t,
    '''        atick: 0,\n        stick: 0,\n    };''',
    '''        atick: 0,\n        stick: 0,\n        sample_pc: 0xffff,\n        sample_live_div: 0xff,\n    };''',
    'TraceEntry defaults',
)

anchor = '''        self.entries[self.len] = TraceEntry {\n'''
insert = '''        // v7.8.7 STALL-PC probe. rel_adv is based on the same advance\n        // origin written to the frame CSV.  During a no-Random transition\n        // stall, measured_div() can remain stale; reader.div() is a direct\n        // read of the emulator-backed live rDIV byte.\n        let sample_rel = rng_advance().wrapping_sub(self.start_advance);\n        let (sample_pc, sample_live_div) = if self.probe_session && sample_rel <= 40 {\n            (reader.pc_reg(), reader.div())\n        } else {\n            (0xffff, 0xff)\n        };\n\n'''
if t.count(anchor) != 1:
    raise SystemExit(f'v787 record anchor: expected 1 match, got {t.count(anchor)}')
t = t.replace(anchor, insert + anchor, 1)

t = rep(
    t,
    '''            atick: adiv_tick(),\n            stick: sdiv_tick(),\n        };''',
    '''            atick: adiv_tick(),\n            stick: sdiv_tick(),\n            sample_pc,\n            sample_live_div,\n        };''',
    'TraceEntry capture',
)

t = rep(
    t,
    '''            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species\\n"''',
    '''            "frame,rel_adv,advance,state,div,adiv,sdiv,acyc,scyc,asub,ssub,asub_dec,ssub_dec,ap4,sp4,atick,stick,keys,a_pressed,d235,d236,d237,d238,d239,d23a,d23b,d23c,d23d,d23e,watch_changed,celebi_species,sample_pc,sample_live_div\\n"''',
    'frame CSV header',
)

t = rep(
    t,
    '''            let _ = write!(\n                line,\n                "{},{}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8\n            );''',
    '''            let _ = write!(\n                line,\n                "{},{},{:04X},{:02X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div\n            );''',
    'frame CSV tail',
)

# Compact lineage marker in the CSV without changing the existing v7.8.6
# neutral-probe row layout.
needle = '''        // Second section: every Random call, which is what shows how the DVs\n'''
marker = '''        line.clear();\n        let _ = write!(line, "\\nstall_pc_probe,version,window\\nSTALLPC,V787,rel0-40\\n");\n        pnp::trace_file_write(line.as_bytes());\n\n'''
if t.count(needle) != 1:
    raise SystemExit(f'v787 marker anchor: expected 1 match, got {t.count(needle)}')
t = t.replace(needle, marker + needle, 1)

T.write_text(t)
print('Applied v7.8.7 Stall-PC probe: read-only sample_pc + sample_live_div for rel0-40')
