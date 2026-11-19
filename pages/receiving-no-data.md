# Receiving no data (stale table)

Domain: {{domain}}

Synonyms:
- stale table
- data not refreshed
- late data
- table not updating
- gone quiet

Description:
A table that normally updates on a schedule has gone more than twice its usual gap without a write. It looks fine, but its data is old.

## Definition
A table is stale when the time since its last write is more than twice its usual gap between writes. Only tables written on a recurring basis (3 or more separate hours in the last 30 days) are tracked.

## How we measure it
`is_stale` and `stale_tables` in the metric view `mv_table_freshness`.

## Common causes
- The job that writes it is failing
- An upstream feed (MuleSoft, BigQuery) stopped delivering
- The schedule was paused

## Related assets
- {{catalog}}.{{schema}}.mv_table_freshness
- {{catalog}}.{{schema}}.table_freshness

## Sources
- Genie One Job Ops project (pages/receiving-no-data.md)
