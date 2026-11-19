# Prerequisites

Do these once per workspace before `./scripts/deploy.sh`. Who does each step is in brackets.

## 0. Tools [whoever deploys]

- **Databricks CLI v1.21.0 or newer** (latest as of 2026-10-20): `brew upgrade databricks`, then `databricks --version`.
  `deploy.sh` and `run_local.sh` refuse to run on an older CLI.
- `uv` (Python), and Node 18+ only if you change the app's frontend.

## 1. Previews [workspace admin + account admin]

The full list — every preview and setting, where it lives (account vs. workspace), its API key and its status on FEVM —
is in **[PREVIEWS.md](PREVIEWS.md)**. Check a workspace with `./scripts/check_previews.sh <profile>`.

The ones most often missed:
- **Account console:** *Enhanced Unity AI Gateway* (UC Skills), *Pages*, *Databricks One Mobile*, partner-powered AI.
- **Workspace:** *Unity Gateway Skills* and *Unity Gateway skills in Genie* (both needed for shared skills),
  *Managed MCP Servers*, *On-behalf-of-user authorization for apps*, and *Genie ZeroOps* (only after enrollment).

## 2. Identity that runs the deploy [workspace admin]

The person (or service principal) running `deploy.sh` needs:

- **Workspace admin** — writes Genie One's workspace instructions (`/Workspace/.genie_workspace_instructions.md`).
- **`SELECT` on `system.lakeflow` and `system.access`** — the views run with their owner's rights. Grant with
  `GRANT USE SCHEMA, SELECT ON SCHEMA system.lakeflow TO <deployer>` (same for `system.access`) as a metastore admin.
- **`USE CATALOG`, `CREATE SCHEMA`** on the target catalog (or ownership of the schema).
- **`CREATE CONNECTION` on the metastore** — for the MCP connection. If missing, `job_ops_register_mcp` stops with
  the exact `GRANT` to send your metastore admin:
  `GRANT CREATE CONNECTION ON METASTORE TO \`<deployer>\``.
- **Account-level tag policy** permission (or an existing governed tag) for the Genie One domain. If the account
  already has a suitable governed tag, pass it with `--var "domain_tag_key=<tag>"`.
- Optional: `SELECT` on `system.data_quality_monitoring` if you want the table-health skill to show monitoring results.

## 3. Genie ZeroOps [account team]

ZeroOps is in Private Preview. Three steps:
1. The account team posts the workspace ID in `#genie-zeroops` to get it enrolled.
2. A workspace admin turns on **ZeroOps** on the workspace **Previews** page (it is not an account-level toggle).
3. Job owners open **Jobs & Pipelines**, find the ZeroOps banner at the top, and use **Configure** to add their jobs.
"Open in ZeroOps" links to that Jobs & Pipelines page (`{host}/jobs?o={workspace_id}`); override with
`--var "zeroops_url=..."` if needed.

## 4. Models

Genie One needs partner-powered models (or the workspace's approved alternatives) enabled.
