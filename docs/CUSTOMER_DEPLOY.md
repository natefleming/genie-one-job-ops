# Deploying into a customer workspace

Step by step. Nothing here touches existing jobs or data — it only reads system tables and creates objects in one schema.

## 1. Sign in

```bash
databricks auth login --host https://<customer-workspace>.azuredatabricks.net --profile customer
databricks current-user me -p customer        # confirm you're you
```

## 2. Pick the catalog and schema

Use a catalog you can create a schema in (e.g. a shared ops catalog). Defaults are `retail_consumer_goods.job_ops`
— override both:

```bash
CATALOG=<their_catalog>
SCHEMA=genie_job_ops
```

## 3. Check prerequisites

Work through [PREREQS.md](PREREQS.md) and turn on the previews in [PREVIEWS.md](PREVIEWS.md) — then confirm with
`./scripts/check_previews.sh customer`. The two that most often need someone else: **metastore admin** for
`SELECT` on `system.lakeflow`/`system.access` and **`CREATE CONNECTION`**.

## 4. Deploy (no demo workloads)

```bash
./scripts/deploy.sh customer $CATALOG --schema $SCHEMA
```

Optional variables (add `--var key=value`):

| Variable | Default | Set it when |
|---|---|---|
| `ops_group` | `account users` | Only a specific group (e.g. `data-platform-ops`) should use Job Ops |
| `warehouse_id` | lookup "Serverless Starter Warehouse" | They use a different SQL warehouse |
| `domain_tag_key` | `Data Platform Operations` | They already have a governed tag for domains |
| `zeroops_url` | `{host}/jobs?o={workspace_id}` | The ZeroOps inbox lives at a different path |
| `refresh_schedule` | `UNPAUSED` | Pause the 15-minute snapshot refresh |

Monitoring several workspaces? Set the `workspace_ids` parameter on the `data_layer` and refresh tasks (comma-separated);
run links only open for the current workspace.

## 5. Finish in the UI (10 minutes)

1. **Pages** — import the 9 pages into the *Data Platform Operations* domain: [PAGES.md](PAGES.md).
2. **Skills** — each user (or a pilot group) installs the 7 Job Ops skills: Genie One → **Customizations → Skills** →
   Browse → `<catalog>.<schema>`. (Install-by-default is on the Genie roadmap.)
3. **MCP tools** — in a Genie One chat, **+ → Tools**, add `mcp_mulesoft`, `mcp_gcp`, `mcp_job_ops`.
4. **Error text in the app** — grant the two app service principals **CAN VIEW** on the jobs and pipelines you want
   error details for (the register job does this automatically for jobs tagged `source_system`).
5. **Teams / Mobile / external MCP clients** — [CONSUMPTION.md](CONSUMPTION.md).

## 6. Connect the real MuleSoft MCP server

The mock answers for MuleSoft until you swap it:

1. Get the MuleSoft MCP server URL and OAuth details from the integration team (Anypoint MCP server, connected app).
2. Create a UC HTTP connection to it — **OAuth U2M** if each user should see MuleSoft with their own access, M2M if a
   shared integration account is fine.
3. Point the `mcp_mulesoft` MCP service at that connection (Catalog Explorer → the service → Edit), or re-create it
   with `include_tool_selectors` limited to the read-only tools.
4. Update `skills/integration-status/SKILL.md` with the real tool names and re-run `job_ops_setup` (it re-publishes skills).

## 7. Verify

```bash
databricks genie ask "What jobs are broken right now and what kind of failure is each one?" -p customer
```

Open the Job Ops app (URL printed by `deploy.sh`), click the **✦ Genie** button, and ask about the page you're on.

## Remove everything

```bash
databricks bundle destroy -p customer --var catalog=$CATALOG --var schema=$SCHEMA
```
Then drop the schema, the Genie Agent "Job Ops", the domain and the Job Ops block in `/Workspace/.genie_workspace_instructions.md`.
