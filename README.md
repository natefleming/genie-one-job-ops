# Genie One Job Ops

An agentic way to **monitor and resolve failed jobs and pipelines**, built on **Genie One**. People ask in plain English
— in Genie One, Teams/Copilot, the Genie One mobile app, any MCP client, or the Job Ops web app — and get:

1. **What broke** — jobs, nested tasks and pipelines, grouped into plain-English failure categories
2. **Why** — the actual error, upstream causes (MuleSoft flows, GCP/BigQuery), and history
3. **Who is affected** — downstream tables, jobs, dashboards and Genie agents from Unity Catalog lineage
4. **How to fix it** — a link to repair the run in Databricks (your own permissions) and to **Genie ZeroOps** for the root cause and code fix

Everything ships as one Declarative Automation Bundle plus a wrapper script, tested on FEVM and parameterized for
the customer workspace.

```
 Users ── Genie One (web · Teams/Copilot · Mobile · MCP clients) ──┐        ┌── Job Ops app (FastAPI + React, OBO)
                                                                   ▼        ▼          with the Genie side panel
         Genie One  ←  workspace instructions · UC Skills (7) · Domain + Pages
             │
             ├── Job Ops Genie Agent ── metric views ── snapshots (15 min) ── system.lakeflow / system.access
             ├── UC functions: failing_now · run_tasks · downstream_impact · run_links
             └── UC MCP services: mcp_mulesoft · mcp_gcp · mcp_job_ops  ──►  integrations MCP app (mock → real MuleSoft)
                                                                   resolve ──►  Repair run in Databricks · Genie ZeroOps
```

## Layout

| Path | What it is |
|---|---|
| `databricks.yml` | Bundle root — variables (catalog, schema, warehouse, app names, ZeroOps URL, …), one generic target |
| `resources/` | Jobs: `job_ops_setup`, `job_ops_refresh` (every 15 min), `job_ops_register_mcp`; apps: `job_ops_app`, `integrations_mcp` |
| `src/sql/` | `01` taxonomy + base views over system tables · `02` snapshots · `03` metric views · `04` functions |
| `src/notebooks/` | Setup steps: data layer, Genie Agent, domain, UC Skills, workspace instructions, MCP registration |
| `src/genie_workspace_instructions.md` | The block added to Genie One's workspace-wide instructions |
| `skills/<name>/SKILL.md` | The 7 Genie One skills (published to Unity Catalog with catalog/schema filled in) |
| `pages/*.md` | The 9 Genie One Pages (templates in the Genie Code bulk-import layout; render, then upload — `docs/PAGES.md`) |
| `app/` | Job Ops web app: `server.py` (FastAPI) + `frontend/` (React, built into `static/`) |
| `mcp_mock/` | Integrations MCP server: mock MuleSoft + GCP tools, real job-error tool |
| `demo_workloads/` | Separate bundle of retail-flavored jobs that fail on purpose — **test workspaces only** |
| `scripts/deploy.sh` | One-command deploy into any workspace |
| `scripts/check_previews.sh` | Check that a workspace has the required previews on |
| `scripts/render_pages.sh` | Render `pages/` for a workspace (domain + catalog/schema) for upload |
| `scripts/run_local.sh` | Run the Job Ops app (and MCP server) locally against a workspace |
| `presentation/` | Optional, not in the repo: a customer deck the build copies into the app at `/presentation/` |
| `docs/` | `PREVIEWS.md`, `PREREQS.md`, `CUSTOMER_DEPLOY.md`, `APPS.md`, `PAGES.md`, `CONSUMPTION.md` |

## Quick start (FEVM)

```bash
./scripts/deploy.sh fevm retail_consumer_goods --with-demo --var "domain_tag_key=Operational Resilience"
# break the demo, wait ~15 min for system tables + the snapshot refresh, then ask Genie One "what's broken?"
(cd demo_workloads && databricks bundle run chaos -p fevm --params scenario=break)
```

FEVM notes: the shared account is at its tag-policy limit, so the domain reuses the existing `Operational Resilience`
governed tag; and MCP registration needs a metastore admin to grant CREATE CONNECTION (see `docs/PREREQS.md`).

### Before a demo

To make the live demo tell a clean story:
1. **MCP registered** (`job_ops_register_mcp` succeeded). Without it Genie One can't check MuleSoft and Google Cloud,
   which is part of the story.
2. **Give web events a history.** "Gone quiet" needs writes in 3+ separate hours: run `chaos` with `scenario=heal`, leave
   the hourly web events job running healthy for 3+ hours, then break.
3. **Break the morning of the demo**, so each story job has failed once and the snapshot (15 min) has caught up.
4. On a shared workspace other teams' jobs fail too: ask about the demo jobs by their prefix (`job_prefix`, default
   `Acme`: "what Acme jobs broke overnight?").
5. Redeploy with `deploy.sh … --with-demo`, not a bare `bundle deploy`, so the MCP mock keeps its demo flags.

Set the company name shown in the app and used by the Genie Agent with `--var company_name=...`. Customer workspace
targets go in a gitignored `targets.local.yml` (template: `targets.local.yml.example`). For a customer workspace see **[docs/CUSTOMER_DEPLOY.md](docs/CUSTOMER_DEPLOY.md)**. To run the apps on your laptop
(`./scripts/run_local.sh <profile>`) or redeploy them to Databricks Apps, see **[docs/APPS.md](docs/APPS.md)**.

## Design decisions

- **Genie One does the work, through skills and governed data** — no custom agent code. The skills tell Genie which
  metric view, function or MCP tool to use and how to answer; the workspace instructions make it the default for everyone.
- **Snapshots, not live system-table queries.** The base views recompute 90 days of account-wide history (10–45 s);
  `job_ops_refresh` snapshots them every 15 minutes so answers come back in 1–3 s. System tables already lag a few minutes.
- **Views run with the owner's rights.** Users need access to this schema only — not to `system.*`.
- **Re-runs are links, not API calls.** Databricks Apps user tokens can't carry a Jobs API scope, and a service principal
  re-running jobs would hide who did it. The user opens the run and clicks **Repair run**; Databricks checks their permission.
- **ZeroOps by deep link.** ZeroOps has no incident API, system table or webhook yet (notifications are next, an API
  later), so we link to the ZeroOps inbox and use the same vocabulary. When the API lands, a skill can pull the RCA in.
- **MCP by prefix.** One MCP server, three Unity Catalog MCP services (`mulesoft_*`, `gcp_*`, `job_*`) so each can be
  granted and swapped independently — e.g. point `mcp_mulesoft` at the real MuleSoft MCP server.
- **Genie Agent and UC Skills from the setup job, not bundle resources.** CLI 1.21 has a `genie_spaces` resource, but
  creating a space checks that its tables exist, and on a fresh workspace the metric views don't exist until the setup
  job has run, so the first `bundle deploy` would fail. Skills have no bundle resource yet. The setup job creates both in
  the right order and is safe to re-run.
