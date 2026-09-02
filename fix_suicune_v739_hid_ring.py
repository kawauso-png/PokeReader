#!/usr/bin/env python3
from pathlib import Path

H=Path('3gx/sources/hid.c')
M=Path('3gx/sources/main.c')
T=Path('reader_core/src/crystal/trace.rs')
h=H.read_text(); m=M.read_text(); t=T.read_text()

def rep(x,a,b,label,count=1):
    n=x.count(a)
    if n!=count: raise SystemExit(f'v739 {label}: expected {count}, got {n}')
    return x.replace(a,b)

def need(x,s,label):
    if s not in x: raise SystemExit('v739 missing '+label+': '+s[:120])

old_h='''#include <3ds.h>\n\nvu32 *g_key_addr = 0;\nu32 g_current_keys = 0;\nu32 g_previous_keys = 0;\n\nvoid set_key_addr(vu32 *key_addr)\n{\n  g_key_addr = key_addr;\n}\n\nvoid scan_input()\n{\n  if (g_key_addr != 0)\n  {\n    g_previous_keys = g_current_keys;\n    g_current_keys = *g_key_addr;\n  }\n}\n\nu32 get_current_keys()\n{\n  return g_current_keys;\n}\n\nu32 get_previous_keys()\n{\n  return g_previous_keys;\n}\n'''
new_h='''#include <3ds.h>\n\n// v7.3.9: g_hid_shared_mem is the base of the 3DS HID shared-memory block.\n// HID PAD data is an 8-entry ring.  The current entry is selected by word 4;\n// keys live at word 10 + id*4.  Reading a fixed +0x28 slot (word 10) was\n// intermittently stale and is the root cause of TEST HOLD UP not reacting.\nvu32 *g_hid_shared_mem = 0;\nu32 g_current_keys = 0;\nu32 g_previous_keys = 0;\nu32 g_hid_ring_index = 0;\nu32 g_hid_ring_resamples = 0;\n\nvoid set_key_addr(vu32 *hid_shared_mem_base)\n{\n  g_hid_shared_mem = hid_shared_mem_base;\n}\n\nstatic u32 read_hid_pad_current(void)\n{\n  // The HID producer can advance the ring while we are sampling. Read the\n  // selector twice and retry on a boundary so keys and id belong together.\n  for (u32 tries = 0; tries < 3; tries++)\n  {\n    u32 id0 = g_hid_shared_mem[4];\n    if (id0 > 7) id0 = 7;\n    u32 keys = g_hid_shared_mem[10 + id0 * 4];\n    u32 id1 = g_hid_shared_mem[4];\n    if (id1 > 7) id1 = 7;\n    if (id0 == id1)\n    {\n      g_hid_ring_index = id1;\n      return keys;\n    }\n    g_hid_ring_resamples++;\n  }\n\n  u32 id = g_hid_shared_mem[4];\n  if (id > 7) id = 7;\n  g_hid_ring_index = id;\n  return g_hid_shared_mem[10 + id * 4];\n}\n\nvoid scan_input()\n{\n  if (g_hid_shared_mem != 0)\n  {\n    g_previous_keys = g_current_keys;\n    g_current_keys = read_hid_pad_current();\n  }\n}\n\nu32 get_current_keys()\n{\n  return g_current_keys;\n}\n\nu32 get_previous_keys()\n{\n  return g_previous_keys;\n}\n\nu32 get_hid_ring_index()\n{\n  return g_hid_ring_index;\n}\n\nu32 get_hid_ring_resamples()\n{\n  return g_hid_ring_resamples;\n}\n'''
h=rep(h,old_h,new_h,'hid.c fixed-slot reader')

# map_input_hook receives the HID shared-memory base.  Older builds stored only
# addr+0x28, i.e. ring entry zero.  Pass the base so scan_input can select the
# producer's actual current slot exactly like libctru hidScanInput().
m=rep(m,'set_key_addr((vu32 *)(addr + 0x28));','set_key_addr((vu32 *)addr);','HID base mapping')

# Epoch/UI only. RNG/search/rebind model is intentionally unchanged from v7.3.8.
t=t.replace('S738','S739')
t=t.replace('EXEC,V738','EXEC,V739')
t=t.replace('GLOBALBEAM,V738','GLOBALBEAM,V739')
t=t.replace('SOFTRESET,V738','SOFTRESET,V739')

for s in ['S739 TEST HOLD UP 0.5s','EXEC,V739','GLOBALBEAM,V739','SOFTRESET,V739']:
    need(t,s,s)
if 'S738' in t: raise SystemExit('v739 stale S738 UI')

H.write_text(h); M.write_text(m); T.write_text(t)
print('Applied v7.3.9: HID PAD current-ring sampling replaces stale fixed +0x28 slot; v7.3.8 RNG/search logic preserved')
