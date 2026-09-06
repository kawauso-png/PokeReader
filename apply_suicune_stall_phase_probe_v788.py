#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()


def rep(src: str, old: str, new: str, label: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v788 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.8.8 extends v7.8.7 observation only. No input/RNG/DIV/DV/save value is
# written. The four v7.8.7 runs showed that all transport divergence is
# concentrated in the last present of the rel27 stall. Add the emulator F604
# M-cycle subtick and JP Crystal hROMBank so offline analysis can reconstruct
# the exact live DIV:subtick phase and resolve banked PCs >= 4000.
#
# JP hROMBank = FF9D. This is the same JP HRAM +0x0B shift independently
# confirmed by hJoypadDown=FFA4 and hJoyDown=FFA8 in the existing JOYMAP probe.

# Extend TraceEntry.
t = rep(
    t,
    '''    pub sample_pc: u16,\n    pub sample_live_div: u8,\n}''',
    '''    pub sample_pc: u16,\n    pub sample_live_div: u8,\n    /// v7.8.8: direct emulator M-cycle subtick and JP current ROM bank.\n    pub sample_live_sub: u8,\n    pub sample_rom_bank: u8,\n}''',
    'TraceEntry fields',
)

t = rep(
    t,
    '''        sample_pc: 0xffff,\n        sample_live_div: 0xff,\n    };''',
    '''        sample_pc: 0xffff,\n        sample_live_div: 0xff,\n        sample_live_sub: 0xff,\n        sample_rom_bank: 0xff,\n    };''',
    'TraceEntry defaults',
)

old_sample = '''        let (sample_pc, sample_live_div) = if self.probe_session && sample_rel <= 40 {\n            (reader.pc_reg(), reader.div())\n        } else {\n            (0xffff, 0xff)\n        };'''
new_sample = '''        let (sample_pc, sample_live_div, sample_live_sub, sample_rom_bank) =\n            if self.probe_session && sample_rel <= 40 {\n                (\n                    reader.pc_reg(),\n                    reader.div(),\n                    pnp::read::<u8>(0x0022f604),\n                    gb_mem::read_u8(0xff9d),\n                )\n            } else {\n                (0xffff, 0xff, 0xff, 0xff)\n            };'''
t = rep(t, old_sample, new_sample, 'sample tuple')

t = rep(
    t,
    '''            sample_pc,\n            sample_live_div,\n        };''',
    '''            sample_pc,\n            sample_live_div,\n            sample_live_sub,\n            sample_rom_bank,\n        };''',
    'TraceEntry capture',
)

t = rep(
    t,
    '''celebi_species,sample_pc,sample_live_div\\n"''',
    '''celebi_species,sample_pc,sample_live_div,sample_live_sub,sample_rom_bank\\n"''',
    'frame CSV header',
)

t = rep(
    t,
    '''                "{},{},{:04X},{:02X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div\n            );''',
    '''                "{},{},{:04X},{:02X},{:02X},{:02X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div,\n                entry.sample_live_sub,\n                entry.sample_rom_bank\n            );''',
    'frame CSV tail',
)

needle = '''        // Second section: every Random call, which is what shows how the DVs\n'''
marker = '''        line.clear();\n        let _ = write!(line, "\\nstall_phase_probe,version,window,subtick_addr,hrombank\\nSTALLPHASE,V788,rel0-40,0022F604,FF9D\\n");\n        pnp::trace_file_write(line.as_bytes());\n\n'''
if t.count(needle) != 1:
    raise SystemExit(f'v788 marker anchor: expected 1 match, got {t.count(needle)}')
t = t.replace(needle, marker + needle, 1)

T.write_text(t)
print('Applied v7.8.8 Stall-Phase probe: live DIV + F604 subtick + JP hROMBank')
