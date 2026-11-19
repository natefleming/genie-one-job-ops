# Previews and settings to enable

Everything Job Ops depends on that is a **preview** or a **non-default setting**, where to switch it on, and the status
on the FEVM test workspace. Check a workspace automatically with:

```bash
./scripts/check_previews.sh <profile>      # reads the workspace Previews page through the settings API
```

Status legend for FEVM (`fevm-nfleming-stable-aws`, workspace `7474649850651417`), checked **2026-10-19**:
- **On (API)** — read from `workspace-settings-v2`
- **On (UI)** — seen on the Previews page (screenshot), not exposed by the API
- **Unverified** — account-level or not in the API; check by hand
- **Off** — currently disabled

## Required

| Preview / setting (as named in the UI) | Where | API key | Needed for | FEVM |
|---|---|---|---|---|
| **Genie One** — chat with agents and sources from one conversation | Workspace → Previews | `one_chat` | Everything in Genie One, including the app's ✦ Genie panel | On (API) |
| **Enhanced Unity AI Gateway** | **Account** console → Previews | — | UC Skills (prerequisite) | Unverified ¹ |
| **Unity Gateway Skills** — "Enables Unity Gateway Skills for a workspace" | Workspace → Previews | — | UC Skills | On (UI) |
| **Unity Gateway skills in Genie** — share skills via Unity Catalog | Workspace → Previews | `genie_uc_skills` | Installing the 7 Job Ops skills in Genie One | On (API) |
| **Unity AI Gateway** | Workspace → Previews | `ai_gateway_ga_ws` | Skills and MCP services are governed through the gateway | On (API) |
| **Managed MCP Servers** | Workspace → Previews | `managed_mcp_servers` | MCP services (MuleSoft, GCP, job errors) in Genie One | On (API) |
| **Pages** (Beta) | **Account** console → Previews | — | The 9 Pages | Unverified |
| **Discover page** | Workspace → Previews | `discover_page` | Creating/finding the domain and Pages | On (API) |
| **Tags for workspace assets** (dashboards, Genie spaces) | Workspace → Previews | `enable_lakeview_tags` | Tagging the Job Ops agent and app into the domain | On (API) |
| **Databricks Apps** | Workspace → Previews | `custom_apps_preview` | Job Ops app, integrations MCP app | On (API) |
| **On-behalf-of-user authorization for apps** | Workspace → Previews | `enable_obo_user_apps` | Job Ops app runs as the signed-in user | On (API) |
| **Allowed app user API scopes** (setting) | Workspace → Settings | `allowedAppsUserApiScopes` | Must allow `sql` and `genie` | `*` (all) |
| **Partner-powered AI features** (setting) | **Account** console → Settings | — | Genie One's models | Unverified ² |

## Required for a specific piece

| Preview / setting | Where | API key | Needed for | FEVM |
|---|---|---|---|---|
| **Genie ZeroOps** (Private Preview) | Workspace → Previews, **after enrollment** ³ | — | "Open in ZeroOps", root cause + fixes | **Not enrolled** |
| **Genie One MCP** | Workspace → Previews | `genie_one_mcp` | Copilot Studio, Claude and other external MCP clients using Genie One | On (API) |
| **Databricks One** | Workspace → Previews | `databricks_one` | Business users with consumer access; mobile | On (API) |
| **Databricks One Mobile** (`one_mobile`) | **Account** console → Previews | — | Genie One mobile app | Unverified |
| **Collaboration platform connectivity** (setting) | Workspace → Settings | `collaboration_platform_connectivity` | Genie in Microsoft Teams | `ALLOW_ALL` |

## Optional (nice to have)

| Preview | API key | What it adds | FEVM |
|---|---|---|---|
| Third Party Connectors for Agents | `third_party_agent_connectors` | Databricks-provided connectors (M365, Slack, …) alongside our MCP services | On (API) |
| Genie Code automations | `genie_code_automations` | Scheduling the `ops-daily-briefing` | On (API) |
| Genie One memory | `genie_one_user_memory` | Remembers each user's preferences | On (API) |
| Genie One file upload | `genie_one_file_upload` | Attach files to a chat (also used for Pages bulk import) | On (API) |
| Genie Ontology | `genie_ontology_snippets` | Auto-generated business context that complements Pages | On (API) |
| Domain recommendations | `domain_recommendations` | Genie-suggested domains on Discover | On (API) |
| Data quality anomaly detection | `anomaly_detection_ws` | Freshness/completeness monitoring for the `table-health-check` skill | On (API) |
| AI Diagnose | `ai_diagnose` | Databricks' built-in job-failure explanations on the run page | On (API) |
| MCP tools in Genie Agents | `mcp_tools_in_genie_agents` | Lets the Job Ops **agent** itself call managed connectors (we use Genie One instead) | Off |
| Genie One code execution | `genie_code_execution` | Analyses beyond SQL in Genie One | Off |

Notes
1. UC Skills publishing and grants work on FEVM through the API, which suggests the account preview is on; the
   `fevm-account` CLI profile isn't signed in, so it wasn't read directly.
2. Genie One answers on FEVM, so partner-powered models are available there.
3. ZeroOps: the account team sends the workspace ID to the ZeroOps PMs (`#genie-zeroops`); then a workspace admin turns
   it on on the **workspace** Previews page (not account level); then job owners use **Configure** in the ZeroOps banner on
   **Jobs & Pipelines**. Per the PM thread, not a toggle you can find before enrollment.

Not previews but also needed — see [PREREQS.md](PREREQS.md): `SELECT` on `system.lakeflow` / `system.access` for the
deployer, `CREATE CONNECTION` on the metastore, and a governed tag (tag policy) for the domain.
