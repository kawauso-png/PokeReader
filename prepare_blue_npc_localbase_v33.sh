#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.3.2 Moltres NPC local-base resync.
# v8.3.1 preserved the pre-NPC K base and residue. Hardware shows residue/DIV
# phase survives, while the local K base can shift. Relearn base from the latest
# 8 clean logical GB transitions and keep only the locked 20F residue.

# Only compare against the current base while READY. During reacquire the old
# pre-NPC base is intentionally ignored.
sed -i 's/        if NPC_LOCK_VALID {/        if NPC_LOCK_VALID \&\& LIVE.ready {/' "$ADPMOD"

# Replace v8.3.1 fast rearm with latest-8 local-base fitting.
awk '
BEGIN { skip = 0 }
/        } else if NPC_LOCK_VALID && COUNT >= NPC_FAST_REARM \{/ {
    print "        } else if NPC_LOCK_VALID && COUNT >= NPC_FAST_REARM {"
    print "            let start_i = COUNT - NPC_FAST_REARM;"
    print "            let mut local_counts = [0u8; 256];"
    print "            for i in start_i..COUNT {"
    print "                let r = row_at_oldest(i);"
    print "                local_counts[r.k as usize] = local_counts[r.k as usize].saturating_add(1);"
    print "            }"
    print "            let mut local_base = 0u8;"
    print "            let mut local_base_hits = 0u8;"
    print "            for k in 0..256usize {"
    print "                if local_counts[k] > local_base_hits {"
    print "                    local_base_hits = local_counts[k];"
    print "                    local_base = k as u8;"
    print "                }"
    print "            }"
    print "            let mut fast_hits = 0u8;"
    print "            for i in start_i..COUNT {"
    print "                let r = row_at_oldest(i);"
    print "                let d = r.k.wrapping_sub(local_base);"
    print "                let special = (r.seq % 20) as u8 == NPC_LOCK_RESIDUE20;"
    print "                let ok = if special { allowed_special(d, r.step, r.gap) } else { allowed_normal(d, r.step, r.gap) };"
    print "                fast_hits = fast_hits.saturating_add(u8::from(ok));"
    print "            }"
    print "            if fast_hits == NPC_FAST_REARM as u8 && s.sub_count != 0 && s.div_lock >= 8 {"
    print "                NPC_LOCK_BASE = local_base;"
    print "                s.base = local_base;"
    print "                s.base_hits = local_base_hits;"
    print "                s.residue20 = NPC_LOCK_RESIDUE20;"
    print "                s.core_hits = fast_hits;"
    print "                s.core_total = NPC_FAST_REARM as u8;"
    print "                s.ready = true;"
    print "            }"
    skip = 1
    next
}
skip {
    if ($0 ~ /^        } else \{$/) {
        print "        } else {"
        skip = 0
    }
    next
}
{ print }
' "$ADPMOD" > "$ADPMOD.tmp"
mv "$ADPMOD.tmp" "$ADPMOD"

sed -i 's/BLUE LEGEND RNG v8.3.1 NPCSYNC/BLUE LEGEND RNG v8.3.2 LOCALBASE/' "$RUST"
sed -i 's/MOLTRES NPC RESYNC/MOLTRES NPC LOCALBASE/' "$RUST"
sed -i 's/"LEGEND,32,/"LEGEND,33,/' "$CTRACE"

# Build-time guards.
grep -q 'if NPC_LOCK_VALID && LIVE.ready' "$ADPMOD"
grep -q 'let start_i = COUNT - NPC_FAST_REARM;' "$ADPMOD"
grep -q 'NPC_LOCK_BASE = local_base;' "$ADPMOD"
