#!/bin/sh
set -eu

src="${1:-3gx/sources/main.c}"
tmp="${src}.v38post.tmp"

awk '
BEGIN { in_append = 0; inserted = 0; removed = 0 }
{
    line = $0

    # The benchmark must not run between Y+X and Fixed start.  That would make
    # the observer perturb the very host phase it is trying to measure.
    if (line == "                    suicune_tick_bench_once();") {
        removed++
        next
    }

    if (line == "static void append_suicune_observe_csv(void)") {
        print line
        in_append = 1
        next
    }

    if (in_append && line == "{") {
        print line
        print "    // Result is already locked here; benchmark cost cannot change DV/w."
        print "    suicune_tick_bench_once();"
        in_append = 0
        inserted++
        next
    }

    print line
}
END {
    if (removed != 1 || inserted != 1) {
        printf("v3.8 post patch validation failed: removed=%d inserted=%d\n", removed, inserted) > "/dev/stderr"
        exit 44
    }
}
' "$src" > "$tmp"

mv "$tmp" "$src"

grep -A3 'static void append_suicune_observe_csv(void)' "$src" | grep -q 'suicune_tick_bench_once();'

echo "Moved v3.8 tick microbenchmark out of execution timing path"
