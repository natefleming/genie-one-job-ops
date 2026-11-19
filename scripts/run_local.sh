#!/usr/bin/env bash
# Run the Job Ops app (and optionally the integrations MCP server) on your laptop against a workspace.
#
#   ./scripts/run_local.sh <profile> [catalog.schema] [--mcp] [--build] [--dev]
#
#   ./scripts/run_local.sh fevm                       # app on http://localhost:8000
#   ./scripts/run_local.sh fevm --mcp                 # + MCP server on http://localhost:8001/mcp
#   ./scripts/run_local.sh fevm --dev                 # + Vite hot reload on http://localhost:5173
#   ./scripts/run_local.sh customer ops.genie_job_ops
#
# Locally there is no Databricks Apps proxy, so every call runs as YOU (your CLI profile) instead of
# the signed-in user. The data layer (job_ops_setup) must already be deployed to the workspace.
# Needs: databricks CLI, uv; Node 18+ only for --build / --dev.
set -euo pipefail

usage() { sed -n '2,14p' "$0"; exit 1; }
[[ $# -ge 1 ]] || usage
PROFILE="$1"; shift
SCHEMA="retail_consumer_goods.job_ops"
if [[ $# -gt 0 && "$1" != --* ]]; then SCHEMA="$1"; shift; fi
MCP=false; BUILD=false; DEV=false
for arg in "$@"; do
  case "$arg" in --mcp) MCP=true ;; --build) BUILD=true ;; --dev) DEV=true ;; *) usage ;; esac
done

# The bundle uses resource types and fields from recent CLI releases; older CLIs fail in confusing ways.
MIN_CLI="1.21.0"
have=$(databricks --version | sed -E 's/[^0-9]*([0-9]+\.[0-9]+\.[0-9]+).*/\1/')
if [[ "$(printf '%s\n' "$MIN_CLI" "$have" | sort -V | head -1)" != "$MIN_CLI" ]]; then
  echo "Databricks CLI $have is too old; need $MIN_CLI or newer (brew upgrade databricks)."; exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATABRICKS_CONFIG_PROFILE="$PROFILE"

if [[ -z "${WAREHOUSE_ID:-}" ]]; then
  WAREHOUSE_ID=$(databricks warehouses list -p "$PROFILE" -o json | python3 -c '
import json, sys
whs = json.load(sys.stdin)
pick = next((w for w in whs if w["name"] == "Serverless Starter Warehouse"), whs[0] if whs else None)
print(pick["id"] if pick else "")')
fi
[[ -n "$WAREHOUSE_ID" ]] || { echo "No SQL warehouse found; set WAREHOUSE_ID=<id>"; exit 1; }
echo "Profile $PROFILE · schema $SCHEMA · warehouse $WAREHOUSE_ID"

if $BUILD || [[ ! -f "$ROOT/app/static/index.html" ]]; then
  (cd "$ROOT/app/frontend" && npm install --silent && npm run build)
fi

PIDS=()
cleanup() { for p in "${PIDS[@]+"${PIDS[@]}"}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

if $MCP; then
  (cd "$ROOT/mcp_mock" && DATABRICKS_APP_PORT=8001 DATABRICKS_WAREHOUSE_ID="$WAREHOUSE_ID" \
     DEMO_FLAGS_TABLE="${DEMO_FLAGS_TABLE:-}" uv run --quiet --with-requirements requirements.txt python server.py) &
  PIDS+=($!)
  echo "MCP server: http://localhost:8001/mcp"
fi

if $DEV; then
  (cd "$ROOT/app/frontend" && npm run dev -- --port 5173) &
  PIDS+=($!)
  echo "UI with hot reload: http://localhost:5173 (API proxied to :8000)"
fi

echo "Job Ops app: http://localhost:8000"
cd "$ROOT/app"
WAREHOUSE_ID="$WAREHOUSE_ID" JOB_OPS_SCHEMA="$SCHEMA" \
  uv run --quiet --with-requirements requirements.txt uvicorn server:app --host 127.0.0.1 --port 8000
