#!/bin/sh
set -eu

src="${1:-build_suicune_prototype_v39.py}"

grep -q 'total=full\*296' "$src"
sed -i 's/total=full\*296/total=full*293/' "$src"
grep -q 'total=full\*293' "$src"
! grep -q 'total=full\*296' "$src"

echo "Corrected 16-frame DIV increment sum: 296 -> 293 in $src"
