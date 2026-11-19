# Where people use it

The same Genie One, skills and governed data behind every surface. Everyone gets answers as themselves — Unity Catalog
decides what they can see.

## Genie One (browser)

`https://<workspace>/genie` (or Databricks One). The workspace instructions route job-health questions to the Job Ops
agent and metric views automatically; installed skills add the step-by-step behavior.

### How Genie One decides what to use

Genie One has no setting that pins it to one agent, skill or domain. On FEVM it used these, in order of effect:

| Lever | What it does here | Deterministic? |
|---|---|---|
| **Unity Catalog permissions** | Genie One only sees agents, tables and skills the user can access. This is how Databricks recommends hiding other agents (e.g. dev copies). | Yes |
| **Workspace instructions** (`/Workspace/.genie_workspace_instructions.md`) | Points job-health questions at the `mv_*` metric views and functions. Genie quotes them ("the right table per workspace instructions"). | Strong hint |
| **UC Skills** | Loaded by description match: `job-failure-triage`, `failure-root-cause`, `resolve-and-rerun` were picked without being named. | Strong hint |
| **Pages in the domain** | Business meaning and synonyms for terms like "broken" or "gone quiet", searched before it writes SQL. | Hint |
| **The question itself** | Naming the table, agent or skill ("using mv_job_runs…") is the most reliable way to steer one answer. The app's ✦ panel adds the page context for this reason. | Strong hint |

Genie One also reuses past conversations (it fetched an earlier chart conversation and copied its query), so answers
improve as people use it. Restricting which agents Genie One searches with a toggle is a known request; it isn't planned
yet, so use UC permissions.

## Job Ops app

URL printed by `deploy.sh`. Overview, what's broken, run detail (the error, task tree, who's affected, how to fix),
data freshness. The **✦ Genie** button on every page opens a side panel that talks to the Job Ops agent about whatever
is on screen — collapsed by default, like the assistant in the Databricks workspace.

## Microsoft Teams / Copilot

Install the **Databricks Genie** app for Teams (Teams admin center → allow the app; Databricks admin → Genie → Teams
integration). Users chat with Genie One in Teams with their own Databricks identity. For Copilot Studio, add Genie as
an MCP tool (below).

## Genie One mobile app

iOS / Android "Databricks One". Needs the `one_mobile` account preview and OneChat enabled on the workspace. Pairs
well with a **scheduled task**: in Genie One, schedule `/ops-daily-briefing` for 7:00 every weekday — the briefing is
written to read on a phone.

## External MCP clients (Copilot Studio, Claude, other agents)

Genie One is exposed through **Genie MCP** (managed MCP server). Point the client at the workspace's Genie MCP endpoint
with OAuth (user identity). The Job Ops MCP services are also callable directly at
`https://<workspace>/ai-gateway/mcp-services/<catalog>.<schema>.mcp_job_ops` for agents that need the raw tools.
