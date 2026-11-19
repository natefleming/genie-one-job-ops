# Nested task (for-each)

Domain: {{domain}}

Synonyms:
- for-each task
- loop task
- iteration
- child task

Description:
A task that runs many times inside one job run, for example once per region. If one iteration fails, the parent task fails and the tasks after it are skipped.

## Definition
A for-each task repeats one step for each item in a list (regions, stores, files). Each repeat is an iteration. One failed iteration fails the whole for-each task, and every task that depends on it is skipped.

## How we see it
- `is_nested = true` in `mv_task_runs`
- `run_tasks(run_id)` lists every task in a run, including iterations and the tasks skipped because of the failure

## Why it matters
The job page shows one red task, but the real cause is in one iteration, e.g. "West region failed, the other three regions were fine." The error text names the iteration's input.

## Related assets
- {{catalog}}.{{schema}}.mv_task_runs
- {{catalog}}.{{schema}}.run_tasks

## Sources
- Genie One Job Ops project (pages/nested-task.md)
