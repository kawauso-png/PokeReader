#!/usr/bin/env python3
from pathlib import Path
P=Path('reader_core/src/crystal/trace.rs')
s=P.read_text()
marker='        // v6.3 authoritative suffix fingerprint.'
m=s.find(marker)
if m<0:
    raise SystemExit('v720 normalize: suffix marker missing')
brace=s.rfind('        }',0,m)
if brace<0:
    raise SystemExit('v720 normalize: PRE block closing brace missing')
end=brace+len('        }')
# Normalize only whitespace between the PRE block close and the v6.3 comment.
# No generated Rust statement is changed.
s=s[:end]+'\n\n\n'+s[m:]
P.write_text(s)
print('Normalized v7.2 PREFP->POSTFP insertion whitespace')
