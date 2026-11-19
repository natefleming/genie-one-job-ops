# Running the apps — Databricks Apps or your laptop

Two apps ship in this bundle. Both run unchanged in **Databricks Apps** and **locally**.

| App | Source | Databricks Apps name (bundle var) | Local URL |
|---|---|---|---|
| Job Ops web app (FastAPI + React) | `app/` | `ops_app_name` → `job-ops` | http://localhost:8000 |
| Integrations MCP server (FastMCP) | `mcp_mock/` | `mcp_app_name` → `mcp-job-ops-integrations` | http://localhost:8001/mcp |

Prerequisite for both: the data layer is deployed (`databricks bundle run job_ops_setup`), because the apps query the
metric views and functions in `<catalog>.<schema>`.

## In Databricks Apps

`./scripts/deploy.sh <profile> <catalog>` does everything. To (re)deploy just the apps:

```bash
databricks bundle deploy -p <profile> --var catalog=<catalog> --var schema=<schema>
databricks bundle run job_ops_app -p <profile> --var catalog=<catalog> --var schema=<schema>
databricks bundle run integrations_mcp -p <profile> --var catalog=<catalog> --var schema=<schema>
```

- App settings come from the bundle (`resources/apps.yml` → `config.env`), not an `app.yaml`: warehouse, schema,
  ZeroOps URL. Change them with `--var`.
- **The Job Ops app runs as the signed-in user** (`user_api_scopes: sql, genie`): each person sees only what Unity
  Catalog allows, and the Genie panel talks to Genie as them. The first visit asks the user to authorize the app.
- Apps user tokens can't call the Jobs API, so failure error text is read by the app's **service principal**, which
  needs **CAN VIEW** on the jobs (and pipelines) you want details for. `job_ops_register_mcp` grants this for jobs
  tagged `source_system`; grant others in the job's permissions.
- After changing frontend code, rebuild before deploying: `cd app/frontend && npm install && npm run build`
  (the built UI in `app/static/` is what ships — Node is not needed in the workspace).
  The build also copies `presentation/` into the app, so the customer deck is at `/presentation/` (nav link
  **The presentation ↗**); rebuild after editing the deck.
- **The ✦ Genie panel streams Genie One.** It shows each step live (skills loaded, ontology searched, queries run,
  Genie's narration) with a timer and a Stop button, then the answer with numbered citations, **Skills used**,
  **Ontology snippets** and **Sources**. Genie One has no public API yet, so the app uses the endpoint the Databricks CLI
  uses (`/api/2.0/data-rooms/tools/onechat/responses`), isolated in `genie_one_events()` in `app/server.py`. If that
  endpoint is unavailable the panel falls back to the Job Ops Genie Agent and says so (no sources/skills/ontology for
  those answers). Charts Genie One builds (it's asked with `enable_viz`) appear inline as bar/line/area charts with
  hover values and a Table view; the data comes from `GET /api/genie/result/{statement_id}`, read as the user. Each answer
  links to the same conversation in Genie One. Skills link to their Catalog Explorer page, ontology snippets to the Page
  in Discover, and other sources to where Genie One points. Force the fallback with the app env `GENIE_ENGINE=agent` (`resources/apps.yml`). The app's `genie`
  user scope covers both.
- Logs: `databricks apps logs job-ops -p <profile>`. The app logs with loguru (`LOG_LEVEL`, default INFO), and App
  telemetry (Beta) also exports them to `<catalog>.<schema>.job_ops_app_otel_logs` (plus `_metrics`, `_spans`).
- Traces: every Genie turn is one MLflow trace (`databricks-agentbricks` `configure_tracing`/`start_trace`) in the
  experiment `/Users/<deployer>/<ops_app_name>-traces`, stored in `<catalog>.<schema>.job_ops_traces_otel_*`. Inputs are the
  question and page context; outputs are the engine (Genie One or the agent fallback), the answer and its SQL; the trace
  is tagged with the conversation (session) and the user. The setup job's `tracing` task links the experiment to those
  tables and grants the app's service principal `SELECT, MODIFY` on them; run it once after the first deploy:
  `databricks bundle run job_ops_setup --only tracing -p <profile>`.
- Genie lives in the ✦ side panel, which calls Genie through the API — no iframe, so no embedding allowlist is needed.

## On your laptop

```bash
./scripts/run_local.sh <profile>                         # app on :8000 (builds the UI first if needed)
./scripts/run_local.sh <profile> --mcp                   # + the MCP server on :8001
./scripts/run_local.sh <profile> --dev                   # + Vite hot reload on :5173 (API proxied to :8000)
./scripts/run_local.sh <profile> <catalog.schema>        # a different schema
```

- Needs the Databricks CLI (signed in to `<profile>`), `uv`, and Node 18+ for `--build` / `--dev`.
- Locally there is no Apps proxy, so **everything runs as you** (your CLI profile), including the Jobs API calls for
  error text and Genie conversations.
- `WAREHOUSE_ID=<id>` overrides the warehouse (default: "Serverless Starter Warehouse"). For the MCP mock, set
  `DEMO_FLAGS_TABLE=<catalog>.<schema>.demo_flags` to make MuleSoft/GCP answers follow the demo's failure flags.
- Try the MCP server: `npx @modelcontextprotocol/inspector` → Streamable HTTP → `http://localhost:8001/mcp`.
