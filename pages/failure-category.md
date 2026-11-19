# Failure category (data error vs. compute error)

Domain: {{domain}}

Synonyms:
- data error
- compute error
- failure type
- why it failed
- error category

Description:
The plain-English bucket for why a run failed, based on its Databricks termination code.

## Definition
| Category | In plain words | Usually fixed by |
|---|---|---|
| Data Error | The code ran and hit a data problem: bad, late or changed data, a failed check, or a bug. | Fix the data or code, then repair. Genie ZeroOps proposes the fix. |
| Compute Error | The machines running the job failed: crashed, ran out of memory, or the cloud had no capacity. | Repair the run; resize if it repeats. |
| Access & Configuration | The job is set up wrong, points at something missing, or lacks permission. | Fix the job settings or grants. |
| Capacity & Limits | Too much running at once; the run was skipped or queued out. | Spread out schedules. |
| Platform | An unexpected error inside Databricks. | Repair; open a support ticket if it repeats. |

Cancelled runs are not failures.

## How we measure it
`failure_category` on every run in `mv_job_runs`; the code-to-category mapping is the table `failure_taxonomy`.

## Related assets
- {{catalog}}.{{schema}}.failure_taxonomy
- {{catalog}}.{{schema}}.mv_job_runs
- {{catalog}}.{{schema}}.mv_task_runs

## Sources
- Genie One Job Ops project (pages/failure-category.md)
