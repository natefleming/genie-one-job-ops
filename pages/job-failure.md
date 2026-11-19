# Job failure

Domain: {{domain}}

Synonyms:
- failed job
- broken job
- job error
- failed run
- job didn't run

Description:
A Databricks job run that ended in a way someone needs to act on: it failed, errored or timed out. A cancelled run is not a failure.

## Definition
A job run is a failure when its result is Failed, Error or Timed out. "Broken right now" means the job's most recent run failed. A job can fail several times in a row; the number of consecutive failures shows how long it has been broken.

## How we measure it
- `failed_runs` and `failure_rate` in the metric view `mv_job_runs`
- "Broken right now": the function `failing_now(hours)`

## Good to know
- Most failures fall into one of five plain-English categories (see the page *Failure category*).
- System tables can lag the live run by a few minutes.

## Related assets
- {{catalog}}.{{schema}}.mv_job_runs
- {{catalog}}.{{schema}}.failing_now
- {{catalog}}.{{schema}}.failure_taxonomy

## Sources
- Genie One Job Ops project (pages/job-failure.md)
