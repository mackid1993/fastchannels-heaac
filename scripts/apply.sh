#!/usr/bin/env bash
# Add the HE-AAC module to an upstream FastChannels checkout and insert the one hook line.
#   scripts/apply.sh <upstream-checkout>
set -euo pipefail
up=${1:?usage: apply.sh <upstream-checkout>}
root=$(cd "$(dirname "$0")/.." && pwd)
cp "$root/source/app/scrapers/directv_heaac.py" "$up/app/scrapers/directv_heaac.py"
python3 "$root/scripts/insert_hook.py" "$up"
python3 "$root/scripts/insert_hook.py" --check "$up"
# Upstream's own files may differ only by the hook line.
changed=$(git -C "$up" diff --numstat | awk '{print $1"+"$2" "$3}')
[ "$changed" = "1+0 app/__init__.py" ] || { echo "::error::upstream files changed beyond the hook line: $changed"; exit 1; }
echo "Applied: app/scrapers/directv_heaac.py + one hook line."
