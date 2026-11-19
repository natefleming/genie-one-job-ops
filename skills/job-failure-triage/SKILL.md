---
name: job-failure-triage
description: Find out what is broken right now across Databricks jobs and pipelines and sort it by urgency. Use when someone asks "what's broken", "what failed overnight", "any job failures", "is anything down", or wants a status check on jobs or pipelines.
---

# Job failure triage

Give a short, plain-English status of failed jobs and pipelines, most urgent first.

## Steps

1. Get the current failures:
   ```sql
   SELECT * FROM {{catalog}}.{{schema}}.failing_now(24)
   ```
   If the user named a time window ("overnight", "this week"), change the hours (overnight = 12, this week = 168).
2. Get failing child notebooks (started with `dbutils.notebook.run` from another notebook) in the same window. Each child
   run has its own throwaway job id, so report them per notebook, never as separate broken jobs:
   ```sql
   SELECT notebook_path, failed_runs, succeeded_runs, still_failing, last_failure, failure_category, last_failed_run_url
   FROM {{catalog}}.{{schema}}.failing_notebooks(24)
   ```
3. Get pipeline failures in the same window:
   ```sql
   SELECT pipeline_name, MEASURE(failed_updates) AS failed_updates
   FROM {{catalog}}.{{schema}}.mv_pipeline_updates
   WHERE update_date >= current_date() - 1
   GROUP BY ALL HAVING failed_updates > 0
   ```
4. Rank by urgency: jobs that failed several times in a row first, then anything in the Data Error category (likely bad or late data), then the rest.

## How to answer

- Open with one sentence: how many jobs and pipelines are failing, and whether that is more or less than usual (compare to `MEASURE(failed_runs)` from `{{catalog}}.{{schema}}.mv_job_runs` for the previous 7 days).
- Then a short table: job, what kind of problem (failure_category), failed how many times in a row, since when, and the run link (run_url). List failing child notebooks separately, by notebook name.
- End by offering the next step: "Want me to dig into why <job> failed, or check who is affected downstream?"
- If nothing is failing, say so plainly and mention the last failure that recovered.
