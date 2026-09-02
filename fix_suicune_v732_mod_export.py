#!/usr/bin/env python3
from pathlib import Path
import re

p=Path('reader_core/src/crystal/mod.rs')
s=p.read_text()
if 'suicune_control_pause_cell' in s:
    print('v7.3.2 crystal module export already present')
else:
    pat=r'pub use frame::\{([^}]*)\};'
    matches=list(re.finditer(pat,s))
    if len(matches)!=1:
        raise SystemExit(f'v732 frame export block expected 1 match, got {len(matches)}')
    body=matches[0].group(1).rstrip()
    replacement='pub use frame::{'+body+', suicune_control_pause_cell};'
    s=s[:matches[0].start()]+replacement+s[matches[0].end():]
    p.write_text(s)
    print('v7.3.2 crystal module export appended after full patch chain')
