#!/bin/sh
set -eu

MAIN=3gx/sources/main.c

# v37 expands the existing single-statement target gate into multiple statements.
# The target gate has a following `else`, so make the expanded body one compound
# statement and preserve that else binding.
if grep -q 'v8.3.5 fresh session on Auto Hunt enable' "$MAIN" && ! grep -q 'v8.3.5 Auto Hunt compound body' "$MAIN"; then
    awk '
    /v8\.3\.5 fresh session on Auto Hunt enable/ {
        print "                { /* v8.3.5 Auto Hunt compound body */"
        print
        in_body = 1
        next
    }
    in_body && /blue_autosearch_enabled = !blue_autosearch_enabled;/ {
        print
        print "                }"
        in_body = 0
        next
    }
    { print }
    ' "$MAIN" > "$MAIN.tmp"
    mv "$MAIN.tmp" "$MAIN"
fi

grep -q 'v8.3.5 Auto Hunt compound body' "$MAIN"
