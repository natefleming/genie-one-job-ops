#!/usr/bin/env bash
# Check the workspace previews and settings Job Ops depends on (see docs/PREVIEWS.md).
#
#   ./scripts/check_previews.sh <profile>
#
# Reads the workspace Previews page through the settings API. Account-level previews (Enhanced Unity AI Gateway,
# Pages, Databricks One Mobile, partner-powered AI) and toggles the API doesn't expose (Unity Gateway Skills, Genie
# ZeroOps) are listed at the end to check by hand.
set -euo pipefail
[[ $# -eq 1 ]] || { sed -n '2,8p' "$0"; exit 1; }
PROFILE="$1"

REQUIRED="one_chat genie_uc_skills ai_gateway_ga_ws managed_mcp_servers discover_page enable_lakeview_tags custom_apps_preview enable_obo_user_apps"
FEATURE="genie_one_mcp databricks_one"
OPTIONAL="third_party_agent_connectors genie_code_automations genie_one_user_memory genie_one_file_upload genie_ontology_snippets domain_recommendations anomaly_detection_ws ai_diagnose"

value() {
  databricks workspace-settings-v2 get-public-workspace-setting "$1" -p "$PROFILE" -o json 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("unknown"); sys.exit()
b = (d.get("effective_boolean_val") or d.get("boolean_val") or {}).get("value")
print("on" if b is True else "OFF" if b is False else json.dumps({k: v for k, v in d.items() if k != "name"})[:80])'
}

missing=0
report() {
  local group="$1"; shift
  echo "== $group"
  for key in "$@"; do
    v=$(value "$key")
    printf '  %-32s %s\n' "$key" "$v"
    [[ "$group" == "Required" && "$v" != "on" ]] && missing=$((missing + 1))
  done
  return 0
}

report "Required" $REQUIRED
report "Needed for a specific piece" $FEATURE
report "Optional" $OPTIONAL

echo "== Settings"
printf '  %-32s %s\n' allowedAppsUserApiScopes "$(value allowedAppsUserApiScopes)"
printf '  %-32s %s\n' collaboration_platform_connectivity "$(value collaboration_platform_connectivity)"

cat <<'EOF'
== Check by hand
  Account console → Previews:   Enhanced Unity AI Gateway · Pages · Databricks One Mobile
  Account console → Settings:   Partner-powered AI features
  Workspace → Previews:         Unity Gateway Skills · Genie ZeroOps (appears only after enrollment)
EOF
if [[ $missing -gt 0 ]]; then echo "⚠ $missing required preview(s) not on"; exit 2; fi
echo "All required workspace previews are on."
