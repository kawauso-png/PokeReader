#!/usr/bin/env python3
from pathlib import Path
p=Path('reader_core/src/crystal/trace.rs')
s=p.read_text()
start=s.find('BENCH,V744,')
if start<0:
    raise SystemExit('v744 BENCH row not found')
# The format literal continues to the escaped newline before the closing quote.
end=s.find('\\n",',start)
if end<0:
    raise SystemExit('v744 BENCH row terminator not found')
new='BENCH,V744,' + ','.join(['{}']*22 + ['{:04X}']*4)
s=s[:start]+new+s[end:]
p.write_text(s)
print('Fixed v7.4.4 BENCH CSV format by semantic row bounds: 26 fields / 26 arguments')
