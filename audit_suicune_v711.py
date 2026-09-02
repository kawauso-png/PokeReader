#!/usr/bin/env python3
from pathlib import Path

T = Path('reader_core/src/crystal/trace.rs').read_text()
D = Path('reader_core/src/crystal/draw.rs').read_text()
F = Path('reader_core/src/crystal/frame.rs').read_text()
P = Path('reader_core/src/crystal/practical.rs').read_text()

checks = {
    'S711 scan': 'S711 SCAN' in T,
    'S711 ready': 'S711 READY UP+B' in T,
    'S711 learn': 'S711 LEARN D15' in T,
    'scan split A/C/P': '"A{} C{} P{}"' in T,
    'scan split X/I/E': '"X{} I{} E{}"' in T,
    'ready detail empirical': '"E{} W{} DV{:04X}"' in T,
    'ready detail proven': '"L{} W{} DV{:04X}"' in T,
    'old S710 UI gone': 'S710 SCAN' not in T and 'S710 READY UP+B' not in T,
    'telemetry stable': 'STAGE3,V710' in T and 'BRANCH710,V710' in T,
    'hard guard 40': 'RETRY B40' in T,
    'hard guard 716': 'RETRY B716' in T,
    'hard guard 717': 'RETRY B717' in T,
    'FastValidate retained': 'S658 TEST' in T,
    'recent profiles retained': 'EMP_COUNT:usize=5' in P,
    'AI compact': '"AI {}"' in D,
    'SI compact': '"SI {}"' in D,
    'ST compact': '"ST {:04X}"' in D,
    'ADV compact': '"ADV {}"' in D,
    'TID hidden on RNG': '"TID {}"' not in D.split('pub fn draw_pkx',1)[0],
    'Trace row hidden on RNG': 'Trace {} {} f{}' not in F,
    'Save row hidden on RNG': 'Save {} {:08X}' not in F,
}

# Legacy screenshot clutter should no longer render from the RNG status function.
for marker in ['"Fix ', '"Lab ', '"Probe ', '"LiveSub ', '"TSub ', '"P4 ', '"NO RESULT']:
    checks[f'legacy hidden {marker}'] = marker not in T[T.find('pub fn draw_rng_status'):T.find('pub fn draw(&mut self', T.find('pub fn draw_rng_status'))]

bad = [name for name, ok in checks.items() if not ok]
if bad:
    for name in bad:
        print('FAIL:', name)
    raise SystemExit(1)

print('v7.1.1 AUDIT PASS: compact overlay only; Stage3 logic/telemetry/hard guards retained')
