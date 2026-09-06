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
# and hROMBank for rel0..40. Add the guest mode/state most relevant to the
# rel27 final-present split: hVBlank/LCDC plus compact audio-engine state.
# No game/RNG/DIV/input/save value is written.

t = rep(t,
'''    pub sample_rom_bank: u8,\n}''',
'''    pub sample_rom_bank: u8,\n    pub sample_hvblank: u8,\n    pub sample_lcdc: u8,\n    pub sample_vblank_counter: u8,\n    pub sample_wcur_channel: u8,\n    pub sample_music_playing: u8,\n    pub sample_sfx_priority: u8,\n    pub sample_music_fade: u8,\n    pub sample_ch_flags1: u64,\n    pub sample_ch_duration: u64,\n}''',
'fields')

t = rep(t,
'''        sample_rom_bank: 0xff,\n    };''',
'''        sample_rom_bank: 0xff,\n        sample_hvblank: 0xff,\n        sample_lcdc: 0xff,\n        sample_vblank_counter: 0xff,\n        sample_wcur_channel: 0xff,\n        sample_music_playing: 0xff,\n        sample_sfx_priority: 0xff,\n        sample_music_fade: 0xff,\n        sample_ch_flags1: 0xffffffffffffffff,\n        sample_ch_duration: 0xffffffffffffffff,\n    };''',
'defaults')

old = '''        let (sample_pc, sample_live_div, sample_live_sub, sample_rom_bank) = if self.probe_session && sample_rel <= 40 {\n            (reader.pc_reg(), reader.div(), pnp::read::<u8>(0x0022f604), gb_mem::read_u8(0xff9d))\n        } else {\n            (0xffff, 0xff, 0xff, 0xff)\n        };'''
new = '''        let (sample_pc, sample_live_div, sample_live_sub, sample_rom_bank,\n             sample_hvblank, sample_lcdc, sample_vblank_counter,\n             sample_wcur_channel, sample_music_playing, sample_sfx_priority,\n             sample_music_fade, sample_ch_flags1, sample_ch_duration) =\n            if self.probe_session && sample_rel <= 40 {\n                let mut flags = 0u64;\n                let mut durations = 0u64;\n                for ch in 0..8u32 {\n                    let base = 0xc101u32 + ch * 0x32;\n                    flags |= (gb_mem::read_u8(base + 0x03) as u64) << (ch * 8);\n                    durations |= (gb_mem::read_u8(base + 0x15) as u64) << (ch * 8);\n                }\n                (reader.pc_reg(), reader.div(), pnp::read::<u8>(0x0022f604), gb_mem::read_u8(0xff9d),\n                 gb_mem::read_u8(0xff9e), gb_mem::read_u8(0xff40), gb_mem::read_u8(0xff9b),\n                 gb_mem::read_u8(0xc299), gb_mem::read_u8(0xc100), gb_mem::read_u8(0xc2b6),\n                 gb_mem::read_u8(0xc2a7), flags, durations)\n            } else {\n                (0xffff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,\n                 0xffffffffffffffff, 0xffffffffffffffff)\n            };'''
t = rep(t, old, new, 'capture tuple')

t = rep(t,
'''            sample_rom_bank,\n        };''',
'''            sample_rom_bank,\n            sample_hvblank,\n            sample_lcdc,\n            sample_vblank_counter,\n            sample_wcur_channel,\n            sample_music_playing,\n            sample_sfx_priority,\n            sample_music_fade,\n            sample_ch_flags1,\n            sample_ch_duration,\n        };''',
'entry capture')

t = rep(t,
'''sample_pc,sample_live_div,sample_live_sub,sample_rom_bank\\n"''',
'''sample_pc,sample_live_div,sample_live_sub,sample_rom_bank,sample_hvblank,sample_lcdc,sample_vblank_counter,sample_wcur_channel,sample_music_playing,sample_sfx_priority,sample_music_fade,sample_ch_flags1,sample_ch_duration\\n"''',
'csv header')

t = rep(t,
'''                "{},{},{:04X},{:02X},{:02X},{:02X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div,\n                entry.sample_live_sub,\n                entry.sample_rom_bank\n''',
'''                "{},{},{:04X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:02X},{:016X},{:016X}\\n",\n                (entry.flags & FLAG_WATCH_CHANGED != 0) as u8,\n                (entry.flags & FLAG_CELEBI_SPECIES != 0) as u8,\n                entry.sample_pc,\n                entry.sample_live_div,\n                entry.sample_live_sub,\n                entry.sample_rom_bank,\n                entry.sample_hvblank,\n                entry.sample_lcdc,\n                entry.sample_vblank_counter,\n                entry.sample_wcur_channel,\n                entry.sample_music_playing,\n                entry.sample_sfx_priority,\n                entry.sample_music_fade,\n                entry.sample_ch_flags1,\n                entry.sample_ch_duration\n''',
'csv tail')

needle = 'STALLPHASE,V788,rel0-40'
if needle not in t:
    raise SystemExit('v789 V788 lineage marker missing')
t = t.replace(needle, 'STALLPHASE,V789,rel0-40+vblank+audio', 1)

T.write_text(t)
print('Applied v7.8.9 VBlank/audio probe: read-only hVBlank/LCDC/audio state for rel0-40')
