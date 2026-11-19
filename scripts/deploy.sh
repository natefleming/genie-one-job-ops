#!/usr/bin/env bash
# Deploy Job Ops end to end into one workspace.
#
#   ./scripts/deploy.sh <profile> [catalog] [--schema <schema>] [--with-demo] [--var key=value ...]
#
#   ./scripts/deploy.sh fevm                                    # FEVM testbed (defaults: retail_consumer_goods.job_ops)
#   ./scripts/deploy.sh fevm retail_consumer_goods --with-demo  # ... plus the demo jobs that fail on purpose
#   ./scripts/deploy.sh customer ops --schema genie_job_ops            # customer workspace (no demo)
#
# Extra --var flags are passed to the bundle, e.g. --var "domain_tag_key=Operational Resilience".
# Safe to re-run: every step is idempotent.
set -euo pipefail

usage() { sed -n '2,12p' "$0"; exit 1; }
[[ $# -ge 1 ]] || usage
PROFILE="$1"; shift
CATALOG="retail_consumer_goods"
if [[ $# -gt 0 && "$1" != --* ]]; then CATALOG="$1"; shift; fi
SCHEMA="job_ops"
WITH_DEMO=false
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --schema) SCHEMA="$2"; shift 2 ;;
    --with-demo) WITH_DEMO=true; shift ;;
    --var) EXTRA+=(--var "$2"); shift 2 ;;
    *) usage ;;
  esac
done

# The bundle uses resource types and fields from recent CLI releases; older CLIs fail in confusing ways.
MIN_CLI="1.21.0"
have=$(databricks --version | sed -E 's/[^0-9]*([0-9]+\.[0-9]+\.[0-9]+).*/\1/')
if [[ "$(printf '%s\n' "$MIN_CLI" "$have" | sort -V | head -1)" != "$MIN_CLI" ]]; then
  echo "Databricks CLI $have is too old; need $MIN_CLI or newer (brew upgrade databricks)."; exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VARS=(--var "catalog=$CATALOG" --var "schema=$SCHEMA")
if $WITH_DEMO; then VARS+=(--var "demo_flags_table=$CATALOG.$SCHEMA.demo_flags"); fi
VARS+=("${EXTRA[@]+"${EXTRA[@]}"}")

step() { printf '\n\033[1m▸ %s\033[0m\n' "$*"; }
bundle() { (cd "$ROOT" && databricks bundle "$@" -p "$PROFILE" "${VARS[@]}"); }
demo() { (cd "$ROOT/demo_workloads" && databricks bundle "$@" -p "$PROFILE" --var "catalog=$CATALOG" --var "schema=$SCHEMA"); }

step "Validate ($PROFILE → $CATALOG.$SCHEMA)"
bundle validate

if $WITH_DEMO; then
  step "Demo workloads (test workspaces only)"
  demo deploy
  demo run demo_setup
  demo run chaos --params scenario=heal   # a healthy baseline first
fi

step "Deploy bundle (jobs, apps, source)"
bundle deploy

step "Data layer, Genie Agent, domain, UC skills, workspace instructions"
bundle run job_ops_setup

step "Start the apps"
bundle run integrations_mcp
bundle run job_ops_app

step "Register the MCP services in Unity Catalog"
if ! bundle run job_ops_register_mcp; then
  echo "⚠ MCP registration failed — usually missing CREATE CONNECTION on the metastore. See docs/PREREQS.md, then re-run:"
  echo "    databricks bundle run job_ops_register_mcp -p $PROFILE ${VARS[*]}"
fi

step "Done"
APPS=$(cd "$ROOT" && databricks bundle summary -p "$PROFILE" "${VARS[@]}" -o json \
  | python3 -c 'import json,sys;print(" ".join(a["name"] for a in json.load(sys.stdin)["resources"]["apps"].values()))')
for name in $APPS; do
  databricks apps get "$name" -p "$PROFILE" -o json | python3 -c 'import json,sys;d=json.load(sys.stdin);print("  "+d["name"]+": "+d["url"])'
done
echo "  Next: docs/PAGES.md (import the Pages) and docs/CONSUMPTION.md (Genie One, Teams, Mobile, MCP)."
if $WITH_DEMO; then
  echo "  Break the demo:  (cd demo_workloads && databricks bundle run chaos -p $PROFILE --var catalog=$CATALOG --var schema=$SCHEMA --params scenario=break)"
fi
