#!/usr/bin/env python3
from pathlib import Path

p = Path("reader_core/src/crystal/reader.rs")
text = p.read_text()
old = """    // wEnemyMon d237, confirmed from a live Celebi battle: species FB at d237,\n    // moves at d239-d23c, DVs at d23d/d23e\n    wild_ptr: 0xd237,\n    egg_ptr: 0xdf7b,\n"""
new = """    // wEnemyMon d237, confirmed from a live Celebi battle: species FB at d237,\n    // moves at d239-d23c, DVs at d23d/d23e\n    wild_ptr: 0xd237,\n    // Japanese Crystal has the shorter JP name layout in the daycare block.\n    // wEggMon starts at DEF1; its DVs are DF06/DF07 (+0x15/+0x16).\n    egg_ptr: 0xdef1,\n"""
if new not in text:
    if old not in text:
        raise SystemExit("Japanese Crystal egg_ptr marker not found")
    text = text.replace(old, new, 1)
p.write_text(text)
print("Japanese Crystal egg RAM address set to DEF1 (DVs DF06/DF07)")
