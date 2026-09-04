from pathlib import Path


def braced_block(text, marker):
    a = text.index(marker)
    b = text.index('{', a)
    depth = 0
    for i in range(b, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[a:i + 1]
    raise SystemExit(f'AUDIT FAIL: unclosed block for {marker}')


def need(text, needle, label):
    if needle not in text:
        raise SystemExit(f'AUDIT FAIL: missing {label}: {needle!r}')


hid = Path('3gx/sources/hid.c').read_text()
begin = braced_block(hid, 'u32 hid_up_mask_begin()')
restore = braced_block(hid, 'u32 hid_up_mask_restore()')

# Unexpected stacking is a trial-invalidating sequencing fault, never a silent
# recovery. The old word must be dual-view verified before the new begin aborts.
need(begin, 'Stacking is a sequencing fault', 'stacking fault marker')
need(begin, '*old_pa != old_saved || *g_key_addr != old_saved', 'stack restore dual-view verification')
stack_pos = begin.index('if (g_up_mask_active)')
cap_pos = begin.index('if (!hid_up_mask_capable())')
stack = begin[stack_pos:cap_pos]
need(stack, 'g_up_mask_begin_failures++;', 'stack marks begin failure')
need(stack, 'g_up_mask_restore_failures++;', 'stack restore failure telemetry')
need(stack, 'return 0;', 'stack aborts trial begin')

# If the attempted mask cannot be proven, restoring the original HID word is
# itself verified. An uncertain restore remains active so later hooks retry it.
need(begin, '*pa != original || *g_key_addr != original', 'failed-mask restoration verification')
need(begin, 'g_up_mask_saved = original;', 'failed-mask saved original retained')
need(begin, 'g_up_mask_active = true;', 'failed-mask remains retryable')

# Restore is only considered complete after both physical alias and normal VA
# agree. In particular, active=false must occur after the verification branch.
need(restore, 'if (*pa != saved || *g_key_addr != saved)', 'restore dual-view verification')
verify_pos = restore.index('if (*pa != saved || *g_key_addr != saved)')
clear_pos = restore.index('g_up_mask_active = false;')
if clear_pos < verify_pos:
    raise SystemExit('AUDIT FAIL: restore clears active before dual-view verification')

# Losing g_key_addr must not forget an outstanding mask; later calls can retry.
null_start = restore.index('if (g_key_addr == 0)')
null_end = restore.index('vu32 *pa', null_start)
null_block = restore[null_start:null_end]
if 'g_up_mask_active = false;' in null_block:
    raise SystemExit('AUDIT FAIL: null-address restore forgets outstanding mask')
need(null_block, 'g_up_mask_restore_failures++;', 'null-address restore telemetry')

print('AUDIT PASS: v7.6.7c HID restore remains retryable until dual-view verified')
print('AUDIT PASS: unexpected mask stacking is explicit trial failure, never silent recovery')
