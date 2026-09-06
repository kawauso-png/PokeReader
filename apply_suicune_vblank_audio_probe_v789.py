#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v789 {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.8.9 remains observation-only. v7.8.8 already samples PC, live DIV/F604,
# and hROMBank for rel0..40. Add only verified GB/HRAM interrupt/LCD state:
# hVBlank FF9E, hVBlankCounter FF9B, rLCDC FF40, rIF FF0F, rIE FFFF.
# These are enough to distinguish Normal/SoundOnly/Cutscene VBlank modes and
# whether the LCD/interrupt transition itself explains the rel27 final split.
# No game/RNG/DIV/input/save value is written.

t = rep(t,
'''    pub sample_rom_bank: u8,\n}''',
'''    pub sample_rom_bank: u8,\n    pub sample_hvblank: u8,\n    pub sample_lcdc: u8,\n    pub sample_vblank_counter: u8,\n    pub sample_if: u8,\n    pub sample_ie: u8,\n}''',
'fields')

t = rep(t,
'''        sample_rom_bank: 0xff,\n    };''',
'''        sample_rom_bank: 0xff,\n        sample_hvblank: 0xff,\n        sample_lcdc: 0xff,\n        sample_vblank_counter: 0xff,\n        sample_if: 0xff,\n        sample_ie: 0xff,\n    };''',
'defaults')

old = '''        let (sample_pc, sample_live_div, sample_live_sub, sample_rom_bank) = if self.probe_session && sample_rel <= 40 {\n            (reader.pc_reg(), reader.div(), pnp::read::<u8>(0x0022f604), gb_mem::read_u8(0xff9d))\n        } else {\n            (0xffff, 0xff, 0xff, 0xff)\n        };'''
new = '''        let (sample_pc, sample_live_div, sample_live_sub, sample_rom_bank,\n             sample_hvblank, sample_lcdc, sample_vblank_counter, sample_if, sample_ie) =\n            if self.probe_session && sample_rel <= 40 {\n                (reader.pc_reg(), reader.div(), pnp::read::<u8>(0x0022f604), gb_mem::read_u8(0xff9d),\n                 gb_mem::read_u8(0xff9e), gb_mem::read_u8(0xff40), gb_mem::read_u8(0xff9b),\n                 gb_mem::read_u8(0xff0f), gb_mem::read_u8(0xffff))\n            } else {\n                (0xffff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff)\n            };'''
t = rep(t, old, new, 'capture tuple')

t = rep(t,
'''            sample_rom_bank,\n        };''',
'''            sample_rom_bank,\n            sample_hvblank,\n            sample_lcdc,\n            sample_vblank_counter,\n            sample_if,\n            sample_ie,\n        };''',
'entry capture')

t = rep(t,
'''sample_pc,sample_live_div,sample_live_sub,sample_rom_bank\\n"''',
'''sample_pc,sample_live_div,sample_live_sub,sample_rom_bank,sample_hvblank,sample_lcdc,sample_vblank_counter,sample_if,sample_ie\\n"''',
'csv header')

t = rep(t,
'''                "{},{},{:04X},{:02X},{:02X},{:02X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div,\n                entry.sample_live_sub,\n                entry.sample_rom_bank\n''',
'''                "{},{},{:04X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div,\n                entry.sample_live_sub,\n                entry.sample_rom_bank,\n                entry.sample_hvblank,\n                entry.sample_lcdc,\n                entry.sample_vblank_counter,\n                entry.sample_if,\n                entry.sample_ie\n''',
'csv tail')

needle = 'STALLPHASE,V788,rel0-40'
if needle not in t:
    raise SystemExit('v789 V788 lineage marker missing')
t = t.replace(needle, 'STALLPHASE,V789,rel0-40+vblankirq', 1)

T.write_text(t)
print('Applied v7.8.9 VBlank/IRQ probe: verified read-only hVBlank/LCDC/counter/IF/IE for rel0-40')
