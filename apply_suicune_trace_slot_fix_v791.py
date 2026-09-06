#!/usr/bin/env python3
from pathlib import Path

P = Path('3gx/sources/main.c')
s = P.read_text()

old = '''    u32 slot = index;\n    for (; slot < index + 200; slot++)\n'''
new = '''    u32 slot = index;\n    // v7.9.1: traces can legitimately exceed 0200. The old 200-slot cap\n    // returned success with no open file handle once 0001..0200 existed.\n    for (; slot < index + 10000; slot++)\n'''
if s.count(old) != 1:
    raise SystemExit(f'v791 slot loop: expected 1 match, got {s.count(old)}')
s = s.replace(old, new, 1)

old2 = '''    // Empty the file anyway, in case the size check could not be trusted.\n    if (R_SUCCEEDED(res) && trace_file != 0)\n    {\n        FSFILE_SetSize(trace_file, 0);\n    }\n\n    trace_written_slot = slot;\n    FSUSER_CloseArchive(sdmc);\n\n    if (R_FAILED(res))\n'''
new2 = '''    // If the search exhausted without leaving a file open, fail explicitly.\n    // The old code could fall through with res==success and trace_file==0,\n    // making Rust report SAVE OK while no CSV was ever created.\n    if (trace_file == 0)\n    {\n        trace_last_error = 0xE7910201;\n        FSUSER_CloseArchive(sdmc);\n        fsExit();\n        return 0;\n    }\n\n    // Empty the file anyway, in case the size check could not be trusted.\n    if (R_SUCCEEDED(res))\n    {\n        FSFILE_SetSize(trace_file, 0);\n    }\n\n    trace_written_slot = slot;\n    FSUSER_CloseArchive(sdmc);\n\n    if (R_FAILED(res))\n'''
if s.count(old2) != 1:
    raise SystemExit(f'v791 post-loop guard: expected 1 match, got {s.count(old2)}')
s = s.replace(old2, new2, 1)

P.write_text(s)
print('Applied v7.9.1 trace slot fix: >0200 CSV support + no-handle fail-safe')
