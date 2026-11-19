---
name: table-health-check
description: Check whether tables are healthy - still receiving data on schedule, and whether data quality monitoring is turned on. Use when someone asks "is this table up to date", "which tables stopped getting data", "is the data fresh", or "which tables are governed or monitored".
---

# Table health check

## Steps

1. Freshness (works for any table written by a job or pipeline on a schedule):
   ```sql
   SELECT table_name, MEASURE(max_hours_since_write) AS hours_since_write, MEASURE(avg_typical_gap_hours) AS usual_gap_hours
   FROM {{catalog}}.{{schema}}.mv_table_freshness
   WHERE is_stale GROUP BY ALL ORDER BY hours_since_write DESC
   ```
   For one table, filter `table_name = '<catalog.schema.table>'` instead of `is_stale`.
2. Data quality monitoring results, if the workspace has them enabled and the user has access:
   ```sql
   SELECT table_name, status, freshness.status AS freshness, completeness.status AS completeness, event_time
   FROM system.data_quality_monitoring.table_results
   QUALIFY row_number() OVER (PARTITION BY table_id ORDER BY event_time DESC) = 1
   ```
   If this fails with a permission error, say that data quality results need an admin grant and continue with freshness only.
3. Governed vs. not: a table is "governed" for this purpose when it has an owner tag or data quality monitoring. Check tags in `<catalog>.information_schema.table_tags`.

## How to answer

- Say which tables have gone quiet and for how long, compared with how often they usually update ("normally every hour, nothing for 9 hours").
- For a stale table, name the job or pipeline that writes it (last_writer_id) and offer to check why it failed.
- Suggest turning on data quality monitoring for important tables that are not monitored.
