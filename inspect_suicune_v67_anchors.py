#!/usr/bin/env python3
from pathlib import Path


def block(text, marker):
    pos = text.find(marker)
    if pos < 0:
        print(f'NOT FOUND: {marker}')
        return
    brace = text.find('{', pos)
    if brace < 0:
        print(f'NO BRACE: {marker}')
        return
    depth = 0
    end = None
    for i in range(brace, len(text)):
        if text[i] == '{': depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    print('\n===== ' + marker + ' =====')
    print(text[pos:end if end else pos+5000])


def context(text, marker, before=1800, after=5500):
    pos = text.find(marker)
    print('\n===== context ' + marker + ' =====')
    if pos < 0:
        print('NOT FOUND')
        return
    print(text[max(0,pos-before):min(len(text),pos+after)])

trace = Path('reader_core/src/crystal/trace.rs').read_text()
practical = Path('reader_core/src/crystal/practical.rs').read_text()

block(practical, 'pub fn normal_inc')
block(practical, 'pub fn normal_step')
block(trace, 'fn live_practical_lane')
block(trace, 'fn practical_wait_monitor')
context(trace, 'SEARCH_HORIZON')
context(trace, 'practical_states[count]')
context(trace, 'normal_step(&mut')

print('\n===== practical fields context =====')
pos = trace.find('practical_search_skipped:')
print(trace[max(0,pos-800):pos+1800])
