---
name: lineage-impact
description: Show who and what is affected when a Databricks job fails - the tables it writes and the downstream tables, jobs, pipelines, dashboards and Genie agents that depend on them. Use when someone asks "who is affected", "what does this break", "what's downstream", or "is the dashboard wrong because of this".
---

# Who is affected?

Turn lineage into a business-impact answer.

## Steps

1. Find the job_id (from the conversation, or from `{{catalog}}.{{schema}}.job_runs` by job name).
2. Get the impact:
   ```sql
   SELECT * FROM {{catalog}}.{{schema}}.downstream_impact('<job_id>') ORDER BY hop, asset_type
   ```
   - hop 0 = tables the job writes (these now have missing or old data)
   - hop 1 = what reads those tables directly (tables, jobs, pipelines, dashboards, Genie agents)
   - hop 2 = the next layer of tables
3. If a hop-1 job also failed recently, say so — it is probably failing because of this one. Check with `{{catalog}}.{{schema}}.failing_now(24)`.

## How to answer

- Lead with the headline: "If <job> stays broken, <N> tables, <N> dashboards and <N> other jobs are working from old data."
- List dashboards and Genie agents first (people look at those), then jobs, then tables.
- Name the tables in plain words where you can (e.g. `gold_region_sales` = regional sales reporting).
- Note that lineage covers the last 30 days of activity; assets that have not run in that time will not show.
