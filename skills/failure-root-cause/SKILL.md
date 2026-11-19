---
name: failure-root-cause
description: Explain why a specific Databricks job or pipeline run failed, in plain language, including which task broke, whether bad data, compute, access or an upstream system (MuleSoft, GCP) caused it. Use when someone asks "why did <job> fail", "what happened to <job>", or wants the root cause of a failure.
---

# Why did it fail?

Explain one failure so that a non-engineer understands it, and point to Genie ZeroOps for the deep fix.

## Steps

1. Find the run. If the user gave a job name, take its latest failed run:
   ```sql
   SELECT job_id, run_id, job_name, failure_category, termination_code, failure_meaning, first_step, end_time, run_url
   FROM {{catalog}}.{{schema}}.job_runs
   WHERE job_name ILIKE '%<job name>%' AND is_failure
   ORDER BY start_time DESC LIMIT 1
   ```
2. See which tasks failed, including nested (for-each) tasks and tasks skipped because of the failure:
   ```sql
   SELECT * FROM {{catalog}}.{{schema}}.run_tasks('<run_id>')
   ```
   For a for-each task, rows with `is_retry = true` are automatic retries of an earlier attempt, not another input.
   Count failed iterations without them.
3. Get the actual error message with the `job_get_run_error` tool (pass the run_id). System tables do not store error text.
4. Look for an upstream cause:
   - Are the tables this job reads still fresh? `SELECT * FROM {{catalog}}.{{schema}}.table_freshness WHERE is_stale`
   - If the error mentions a feed, file, API or connection, check the source systems with the `integration-status` skill (MuleSoft flows, GCP/BigQuery).
5. Has this happened before? Count failures of the same job and category in the last 30 days from `{{catalog}}.{{schema}}.mv_job_runs`.

## How to answer

- One sentence first: "<Job> failed because <plain reason>." Translate codes, e.g. RUN_EXECUTION_ERROR = "the code ran and hit a data problem".
- For a for-each, name the input that failed from the error text (e.g. `store_targets_west` → the West region). If it
  was retried, say so ("West failed, and failed again on the automatic retry").
- Then: which task broke, the key line of the error (quote it briefly), what was skipped because of it, and whether an upstream system is the real cause.
- Give the run link (run_url).
- For the detailed root cause and a proposed code fix, recommend opening the incident in **Genie ZeroOps** (use `zeroops_url` from `{{catalog}}.{{schema}}.run_links('<run_id>')`).
- Offer next steps: "Check who is affected?" (lineage-impact) or "How do I re-run it?" (resolve-and-rerun).
- Never guess at an error you did not see. If `job_get_run_error` is unavailable, say so and give the run link.
