#!/usr/bin/env bash
# Fill in the domain and catalog/schema in pages/*.md for upload to Genie One.
#
#   ./scripts/render_pages.sh <catalog.schema> [domain]
#   ./scripts/render_pages.sh retail_consumer_goods.job_ops "Operational Resilience"        # FEVM
#   ./scripts/render_pages.sh ops.genie_job_ops                                             # customer
#
# Writes build/pages/<page>.md (one per page) and build/pages/all-pages.md (all nine, for one bulk import).
set -euo pipefail
[[ $# -ge 1 ]] || { sed -n '2,8p' "$0"; exit 1; }
CATALOG="${1%%.*}"; SCHEMA="${1#*.}"; DOMAIN="${2:-Data Platform Operations}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/pages"; mkdir -p "$OUT"
: > "$OUT/all-pages.md"
for f in "$ROOT"/pages/*.md; do
  sed -e "s/{{catalog}}/$CATALOG/g" -e "s/{{schema}}/$SCHEMA/g" -e "s/{{domain}}/$DOMAIN/g" "$f" > "$OUT/$(basename "$f")"
  { cat "$OUT/$(basename "$f")"; printf '\n---\n\n'; } >> "$OUT/all-pages.md"
done
echo "Rendered $(ls "$ROOT"/pages/*.md | wc -l | tr -d ' ') pages for domain \"$DOMAIN\" → $OUT"
