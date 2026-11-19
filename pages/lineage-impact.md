# Lineage impact (who is affected)

Domain: {{domain}}

Synonyms:
- blast radius
- downstream impact
- what does this break
- who is affected
- downstream

Description:
Everything downstream of a failed job: the tables it writes and the tables, jobs, pipelines, dashboards and Genie agents that read them.

## Definition
If a job is broken, the tables it writes hold old or missing data, and everything that reads those tables is affected too.

## How we measure it
The function `downstream_impact(job_id)`, built on the last 30 days of Unity Catalog lineage:
- hop 0: tables the job writes
- hop 1: what reads those tables directly
- hop 2: the next layer of tables

## Good to know
Lead with dashboards and Genie agents, because that is what people look at. Assets that haven't run in 30 days won't appear.

## Related assets
- {{catalog}}.{{schema}}.downstream_impact
- {{catalog}}.{{schema}}.table_lineage_30d

## Sources
- Genie One Job Ops project (pages/lineage-impact.md)
