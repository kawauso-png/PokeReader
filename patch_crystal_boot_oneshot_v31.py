from pathlib import Path

p = Path('reader_core/src/crystal/boottrace.rs')
s = p.read_text()

repls = {
    '// Crystal HRAM addresses, FF80-based. Keep this table explicit so offline\n// analysis never has to infer which revision/layout was sampled.\n//\n// FF90 hVBlankCounter\n// FF92 hROMBank\n// FF93 hVBlank\n// FF94 hMapEntryMethod\n// FF95 hMenuReturn\n// FF97 hJoypadReleased\n// FF98 hJoypadPressed\n// FF99 hJoypadDown\n// FF9A hJoypadSum\n// FF9B hJoyReleased\n// FF9C hJoyPressed\n// FF9D hJoyDown\n// FF9E hJoyLast\n// FF9F hInMenu\n// FFE1 hRandomAdd\n// FFE2 hRandomSub':
    '// Crystal HRAM layout on the JP VC build. FF80-FF89 is occupied by the\n// preceding OAM-DMA HRAM section, so the main HRAM section starts at FF8A.\n// These addresses are also validated against v3 event snapshots: physical A\n// sets FFA3 (pressed), holds FFA4 (down), and releases through FFA2.\n//\n// FF9B hVBlankCounter\n// FF9D hROMBank\n// FF9E hVBlank\n// FF9F hMapEntryMethod\n// FFA0 hMenuReturn\n// FFA2 hJoypadReleased\n// FFA3 hJoypadPressed\n// FFA4 hJoypadDown\n// FFA5 hJoypadSum\n// FFA6 hJoyReleased\n// FFA7 hJoyPressed\n// FFA8 hJoyDown\n// FFA9 hJoyLast\n// FFAA hInMenu\n// FFE1 hRandomAdd\n// FFE2 hRandomSub',
    'const OFF_RTC_DAY_HI: usize = 0x03;': 'const OFF_RTC_DAY_HI: usize = 0x0d;',
    'const OFF_RTC_DAY_LO: usize = 0x04;': 'const OFF_RTC_DAY_LO: usize = 0x0e;',
    'const OFF_RTC_HOURS: usize = 0x05;': 'const OFF_RTC_HOURS: usize = 0x0f;',
    'const OFF_RTC_MINUTES: usize = 0x06;': 'const OFF_RTC_MINUTES: usize = 0x10;',
    'const OFF_RTC_SECONDS: usize = 0x07;': 'const OFF_RTC_SECONDS: usize = 0x11;',
    'const OFF_H_HOURS: usize = 0x0a;': 'const OFF_H_HOURS: usize = 0x14;',
    'const OFF_H_MINUTES: usize = 0x0c;': 'const OFF_H_MINUTES: usize = 0x16;',
    'const OFF_H_SECONDS: usize = 0x0e;': 'const OFF_H_SECONDS: usize = 0x18;',
    'const OFF_VBLANK_COUNTER: usize = 0x10;': 'const OFF_VBLANK_COUNTER: usize = 0x1b;',
    'const OFF_ROM_BANK: usize = 0x12;': 'const OFF_ROM_BANK: usize = 0x1d;',
    'const OFF_VBLANK: usize = 0x13;': 'const OFF_VBLANK: usize = 0x1e;',
    'const OFF_MAP_ENTRY: usize = 0x14;': 'const OFF_MAP_ENTRY: usize = 0x1f;',
    'const OFF_MENU_RETURN: usize = 0x15;': 'const OFF_MENU_RETURN: usize = 0x20;',
    'const OFF_JOYPAD_RELEASED: usize = 0x17;': 'const OFF_JOYPAD_RELEASED: usize = 0x22;',
    'const OFF_JOYPAD_PRESSED: usize = 0x18;': 'const OFF_JOYPAD_PRESSED: usize = 0x23;',
    'const OFF_JOYPAD_DOWN: usize = 0x19;': 'const OFF_JOYPAD_DOWN: usize = 0x24;',
    'const OFF_JOYPAD_SUM: usize = 0x1a;': 'const OFF_JOYPAD_SUM: usize = 0x25;',
    'const OFF_JOY_RELEASED: usize = 0x1b;': 'const OFF_JOY_RELEASED: usize = 0x26;',
    'const OFF_JOY_PRESSED: usize = 0x1c;': 'const OFF_JOY_PRESSED: usize = 0x27;',
    'const OFF_JOY_DOWN: usize = 0x1d;': 'const OFF_JOY_DOWN: usize = 0x28;',
    'const OFF_JOY_LAST: usize = 0x1e;': 'const OFF_JOY_LAST: usize = 0x29;',
    'const OFF_IN_MENU: usize = 0x1f;': 'const OFF_IN_MENU: usize = 0x2a;',
    'mode,BOOT_ONESHOT_TRACE_V3': 'mode,BOOT_ONESHOT_TRACE_V31',
    'address_map,hVBlankCounter,FF90,hROMBank,FF92,hVBlank,FF93,hMapEntryMethod,FF94,hMenuReturn,FF95,hJoypadReleased,FF97,hJoypadPressed,FF98,hJoypadDown,FF99,hJoypadSum,FF9A,hJoyReleased,FF9B,hJoyPressed,FF9C,hJoyDown,FF9D,hJoyLast,FF9E,hInMenu,FF9F,hRandomAdd,FFE1,hRandomSub,FFE2':
    'address_map,hVBlankCounter,FF9B,hROMBank,FF9D,hVBlank,FF9E,hMapEntryMethod,FF9F,hMenuReturn,FFA0,hJoypadReleased,FFA2,hJoypadPressed,FFA3,hJoypadDown,FFA4,hJoypadSum,FFA5,hJoyReleased,FFA6,hJoyPressed,FFA7,hJoyDown,FFA8,hJoyLast,FFA9,hInMenu,FFAA,hRandomAdd,FFE1,hRandomSub,FFE2',
    'BOOT ONE-SHOT V3': 'BOOT ONE-SHOT V3.1',
}

for old, new in repls.items():
    if old not in s:
        raise SystemExit(f'missing marker: {old[:80]!r}')
    s = s.replace(old, new)

p.write_text(s)
print('patched Boot One-shot v3.1 HRAM layout')
