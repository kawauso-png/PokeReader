#!/bin/sh
set -eu

RUST=reader_core/src/gen1/mod.rs
ADPMOD=reader_core/src/gen1/adaptive_model.rs
FCMOD=reader_core/src/gen1/shiny_forecast.rs
CTRACE=3gx/sources/blue_dvtrace.c

# v8.3.0 Moltres NPC-resync mode.
# Ordinary stretches are exact (DIV E0, S4/D16, H clean), but hRandomAdd/Sub
# occasionally jump while logical GB seq + DIV cadence stay continuous. Treat
# those jumps as NPC Random() consumption.
#
# Cold start remains strict: learn one complete 80-frame model first. Once that
# model has locked, preserve base/residue20 across NPC-style RNG jumps and re-arm
# after only 8 consecutive clean frames. Hard timing/seq/PTR faults still drop
# the lock.

# Dedicated Moltres build: default target is Moltres. Paused DPAD switching stays.
sed -i 's/static u32 blue_legend_target = 0u;/static u32 blue_legend_target = 3u;/' "$CTRACE"

if ! grep -q 'NPC_FAST_REARM' "$ADPMOD"; then
    sed -i '/const DIV_WIN: usize = 16;/a\const NPC_FAST_REARM: usize = 8;' "$ADPMOD"
    sed -i '/static mut LAST_SEQ: u32 = 0;/a\
static mut NPC_LOCK_VALID: bool = false;\
static mut NPC_LOCK_BASE: u8 = 0;\
static mut NPC_LOCK_RESIDUE20: u8 = 0;\
static mut NPC_RESETS: u32 = 0;\
static mut NPC_LAST_RESET_SEQ: u32 = 0;' "$ADPMOD"

    awk '
    /pub fn stats\(\) -> AdaptiveStats/ {
        print "#[derive(Clone, Copy, Default)]"
        print "pub struct NpcResyncStats {"
        print "    pub locked: bool,"
        print "    pub resets: u32,"
        print "    pub clean: u8,"
        print "    pub fast_ready: bool,"
        print "    pub last_reset_seq: u32,"
        print "}"
        print ""
        print "pub fn npc_resync_stats() -> NpcResyncStats {"
        print "    unsafe {"
        print "        NpcResyncStats {"
        print "            locked: NPC_LOCK_VALID,"
        print "            resets: NPC_RESETS,"
        print "            clean: COUNT as u8,"
        print "            fast_ready: NPC_LOCK_VALID && LIVE.ready && COUNT < WIN,"
        print "            last_reset_seq: NPC_LAST_RESET_SEQ,"
        print "        }"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"

    # Hard clear = actual timing/seq/PTR problem. Invalidate persisted model.
    sed -i '/fn clear(seq: u32) {/,/^}/ {
        /LIVE.core_total = 0;/a\        NPC_LOCK_VALID = false;
    }' "$ADPMOD"

    # NPC clear = preserve model, restart only the short clean window.
    awk '
    /pub fn observe\(prev_seq:/ {
        print "fn npc_clear(seq: u32) {"
        print "    unsafe {"
        print "        HEAD = 0;"
        print "        COUNT = 0;"
        print "        CLEAN_TAIL = 0;"
        print "        LAST_SEQ = seq;"
        print "        LIVE.valid = false;"
        print "        LIVE.ready = false;"
        print "        LIVE.clean_tail = 0;"
        print "        LIVE.core_total = 0;"
        print "        NPC_RESETS = NPC_RESETS.wrapping_add(1);"
        print "        NPC_LAST_RESET_SEQ = seq;"
        print "    }"
        print "}"
        print ""
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"

    # infer() failure with normal seq and DIV cadence is treated as NPC Random().
    sed -i '/let Some((first, gap)) = infer(prev_rng, rng) else {/,/};/ {
        s/clear(seq);/if NPC_LOCK_VALID \&\& matches!(step, 0x12 | 0x13) { npc_clear(seq); } else { clear(seq); }/
    }' "$ADPMOD"

    # A plausible infer that violates the learned class is also treated as NPC.
    sed -i '/let k = first.wrapping_sub(div);/a\
        if NPC_LOCK_VALID {\
            let d = k.wrapping_sub(NPC_LOCK_BASE);\
            let special = (seq % 20) as u8 == NPC_LOCK_RESIDUE20;\
            let ok = if special { allowed_special(d, step, gap) } else { allowed_normal(d, step, gap) };\
            if !ok {\
                npc_clear(seq);\
                return LIVE;\
            }\
        }' "$ADPMOD"

    # Preserve the original strict 80F cold-lock. After lock, 8 clean frames with
    # exact locked-class matches + coherent DIV phase are enough to re-arm.
    awk '
    /        s.ready = COUNT == WIN/ {
        print "        let cold_ready = COUNT == WIN"
        getline; print
        getline; print
        getline; print
        getline; print
        getline; print
        getline; print
        getline; print
        print "        if cold_ready {"
        print "            NPC_LOCK_VALID = true;"
        print "            NPC_LOCK_BASE = s.base;"
        print "            NPC_LOCK_RESIDUE20 = s.residue20;"
        print "            s.ready = true;"
        print "        } else if NPC_LOCK_VALID && COUNT >= NPC_FAST_REARM {"
        print "            let mut fast_hits = 0u8;"
        print "            for i in 0..COUNT {"
        print "                let r = row_at_oldest(i);"
        print "                let d = r.k.wrapping_sub(NPC_LOCK_BASE);"
        print "                let special = (r.seq % 20) as u8 == NPC_LOCK_RESIDUE20;"
        print "                let ok = if special { allowed_special(d, r.step, r.gap) } else { allowed_normal(d, r.step, r.gap) };"
        print "                fast_hits = fast_hits.saturating_add(u8::from(ok));"
        print "            }"
        print "            if fast_hits == COUNT as u8 && s.sub_count != 0 && s.div_lock >= 8 {"
        print "                s.base = NPC_LOCK_BASE;"
        print "                s.residue20 = NPC_LOCK_RESIDUE20;"
        print "                s.core_hits = fast_hits;"
        print "                s.ready = true;"
        print "            }"
        print "        } else {"
        print "            s.ready = false;"
        print "        }"
        next
    }
    { print }
    ' "$ADPMOD" > "$ADPMOD.tmp"
    mv "$ADPMOD.tmp" "$ADPMOD"
fi

# High-frequency NPC mode: only CURRENT/+1/+2 matter. Full scan every GB frame,
# eliminating stale NOW candidates while keeping 3DS load much lower than the
# old 16F projection.
sed -i 's/const HORIZON: u8 = 16;/const HORIZON: u8 = 2;/' "$FCMOD"
sed -i 's/const SCAN_EVERY: u8 = 8;/const SCAN_EVERY: u8 = 1;/' "$FCMOD"

# Overlay NPC resync status.
if ! grep -q 'NPC L{} R{} C{} {}' "$RUST"; then
    awk '
    /let dd = adaptive_model::div_diag\(\);/ {
        print "        let npc = adaptive_model::npc_resync_stats();"
        print
        next
    }
    /DIV16 \{:04X\} E\{\} C\{\}/ {
        print
        print "        pnp::println!(color = YELLOW, \"NPC L{} R{} C{} {}\", if npc.locked { 1 } else { 0 }, npc.resets, npc.clean, if npc.fast_ready { \"FAST\" } else { \"COLD\" });"
        next
    }
    { print }
    ' "$RUST" > "$RUST.tmp"
    mv "$RUST.tmp" "$RUST"
fi

sed -i 's/BLUE LEGEND RNG v8.2.5 DIVDIAG/BLUE LEGEND RNG v8.3 NPCSYNC/' "$RUST"
sed -i 's/DIV PHASE DIAG/MOLTRES NPC RESYNC/' "$RUST"
sed -i 's/"LEGEND,30,/"LEGEND,31,/' "$CTRACE"
