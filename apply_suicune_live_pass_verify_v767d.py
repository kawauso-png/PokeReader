from pathlib import Path


def rep(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'v767d {label}: expected 1 match, got {n}')
    return src.replace(old, new, 1)

# v7.6.7d is intentionally a narrow hardware validation of the hook-timed
# mask.  v7.6.7c proved the static safety properties, but its paused preflight
# asks a continuously producer-owned HID shared word to remain cleared long
# enough for a dual-view check.  That is not the timing we actually care about.
# During live operation the clear is issued immediately before the original
# rJOYP reader runs, and Crystal hJoypadDown (FF9A) is the authoritative proof.

HID = Path('3gx/sources/hid.c')
hid = HID.read_text()

# Keep fail-closed sequencing and physical-alias verification, but do not
# require the ordinary VA view to remain equal while HID is free-running.
hid = rep(hid,
          'if (((*pa | *g_key_addr) & KEY_DUP) != 0)',
          'if ((*pa & KEY_DUP) != 0)',
          'mask PA-only immediate verification')
hid = rep(hid,
          'if (*old_pa != old_saved || *g_key_addr != old_saved)',
          'if (*old_pa != old_saved)',
          'stack restore PA-only verification')
hid = rep(hid,
          'if (*pa != original || *g_key_addr != original)',
          'if (*pa != original)',
          'failed-mask restore PA-only verification')
hid = rep(hid,
          'if (*pa != saved || *g_key_addr != saved)',
          'if (*pa != saved)',
          'normal restore PA-only verification')
HID.write_text(hid)

# Remove only the paused clear/restore preflight. Capability is still checked
# at B-arm, and every actual masked rJOYP read still uses hid_up_mask_begin().
MAIN = Path('3gx/sources/main.c')
c = MAIN.read_text()
preflight = '''                // v7.6.7 preflight occurs while still frozen. The game cannot
                // observe this temporary clear; resume only after exact restore.
                if (!hid_up_mask_begin())
                {
                    suicune_live_pass_ready = false;
                    svcSleepThread(1000000);
                    continue;
                }
                if (!hid_up_mask_restore())
                {
                    suicune_live_pass_ready = false;
                    svcSleepThread(1000000);
                    continue;
                }
'''
if c.count(preflight) != 1:
    raise SystemExit(f'v767d paused preflight block count {c.count(preflight)}')
c = c.replace(preflight, '''                // v7.6.7d: no paused write-test. The only meaningful test is
                // the hook-timed clear immediately before Crystal reads rJOYP.
''', 1)
MAIN.write_text(c)

# Stamp output lineage distinctly; CSV layout stays identical to v7.6.7c.
T = Path('reader_core/src/crystal/trace.rs')
t = T.read_text()
t = rep(t, 'LIVEPASS,V767C,', 'LIVEPASS,V767D,', 'CSV version stamp')
T.write_text(t)

print('Applied v7.6.7d: remove paused HID preflight; verify hook-timed mask via FF9A')
