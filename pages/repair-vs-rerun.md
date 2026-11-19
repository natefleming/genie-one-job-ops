# Repair run vs. re-run

Domain: {{domain}}

Synonyms:
- repair run
- re-run
- restart the job
- run now
- rerun

Description:
Repair re-runs only the failed tasks and the ones after them; Run now starts a whole new run. Both are done in Databricks with your own permissions.

## Definition
- **Repair run:** re-runs only the tasks that failed, plus the tasks after them, inside the same job run. Use it when the cause was temporary or has been fixed.
- **Run now:** starts a completely new run of the whole job.

## Who can do it
Anyone with **Can Manage Run** on the job. Genie and the Job Ops app never re-run jobs themselves: they give you the link, and Databricks checks your permission when you click.

## Don't repair yet if
The upstream system is still down, or the data or code problem hasn't been fixed. It will fail again.

## Related assets
- {{catalog}}.{{schema}}.run_links

## Sources
- Genie One Job Ops project (pages/repair-vs-rerun.md)
