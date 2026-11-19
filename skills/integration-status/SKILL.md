---
name: integration-status
description: Check the health of systems that feed Databricks - MuleSoft integration flows and GCP/BigQuery - to see whether a job failed because an upstream feed broke. Use when someone asks about MuleSoft, an integration, a feed, BigQuery, GCP, or "is the source system down".
---

# Integration status

Use the MCP tools registered in Unity Catalog for the source systems.

## Tools

- MuleSoft: `mulesoft_list_flows`, `mulesoft_get_flow_status` (flow name), `mulesoft_recent_errors` (hours).
- GCP / BigQuery: `gcp_service_health`, `gcp_bigquery_job_status` (dataset).

## Steps

1. If the user named a job, find which feed it depends on: job tags in `{{catalog}}.{{schema}}.v_jobs_current` (tag `source_system`), or the error text from `failure-root-cause`.
2. Call the matching tool. If you don't know which system, call `mulesoft_recent_errors` and `gcp_service_health` first.
3. Line up the times: did the upstream error happen just before the Databricks job failed?

## How to answer

- Say plainly whether the source system is the cause: "The MuleSoft inventory flow failed at 02:10, so the 02:30 inventory job had no file to load."
- If the upstream system is still failing, say a re-run will fail again and name the flow's owner team if the tool returns one.
- If the tools are not available, say the integration is not connected and continue with what Databricks shows.
