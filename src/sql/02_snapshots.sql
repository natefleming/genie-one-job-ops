-- Genie One Job Ops — snapshots of the base views.
-- The base views recompute 90 days of system-table history on every query (~10-45 s). These tables
-- hold the same rows and are rebuilt every 15 minutes by the "[Job Ops] refresh" job, so Genie One
-- and the app answer in a second or two. System tables themselves lag by a few minutes, so the
-- extra delay is small. Statements are separated by lines starting with "-- @@".

-- @@
CREATE OR REPLACE TABLE ${catalog}.${schema}.job_runs
COMMENT 'One row per job run over the last 90 days with outcome, failure category, time-to-recover and links. is_notebook_run marks child notebook runs (dbutils.notebook.run); notebook_id says which notebook ran (from lineage, last 30 days; join notebook_paths for the path). Snapshot of v_job_runs, refreshed every 15 minutes.' AS
WITH nb AS (
  SELECT entity_metadata.job_info.job_run_id AS run_id, max(entity_metadata.notebook_id) AS notebook_id
  FROM system.access.table_lineage
  WHERE workspace_id IN (${workspace_ids}) AND event_date >= current_date() - 30 AND entity_type = 'JOB'
    AND entity_metadata.notebook_id IS NOT NULL AND entity_metadata.job_info.job_run_id IS NOT NULL
  GROUP BY 1
)
SELECT v.*, CASE WHEN v.is_notebook_run THEN nb.notebook_id END AS notebook_id, current_timestamp() AS refreshed_at
FROM ${catalog}.${schema}.v_job_runs v LEFT JOIN nb USING (run_id);

-- @@
CREATE OR REPLACE TABLE ${catalog}.${schema}.task_runs
COMMENT 'One row per task run over the last 90 days; is_nested marks for-each iterations and is_retry marks automatic retries of an earlier attempt. Snapshot of v_task_runs, refreshed every 15 minutes.' AS
SELECT v.*, v.task_run_id IN (SELECT task_run_id FROM ${catalog}.${schema}.task_retries) AS is_retry,
       current_timestamp() AS refreshed_at
FROM ${catalog}.${schema}.v_task_runs v;

-- @@
CREATE OR REPLACE TABLE ${catalog}.${schema}.pipeline_updates
COMMENT 'One row per Lakeflow pipeline update over the last 90 days. Snapshot of v_pipeline_updates, refreshed every 15 minutes.' AS
SELECT *, current_timestamp() AS refreshed_at FROM ${catalog}.${schema}.v_pipeline_updates;

-- @@
CREATE OR REPLACE TABLE ${catalog}.${schema}.table_freshness
COMMENT 'Recurring tables with last write, usual gap and is_stale ("receiving no data"). Snapshot of v_table_freshness, refreshed every 15 minutes.' AS
SELECT *, current_timestamp() AS refreshed_at FROM ${catalog}.${schema}.v_table_freshness;

-- @@
CREATE OR REPLACE TABLE ${catalog}.${schema}.table_lineage_30d
COMMENT 'Unity Catalog table lineage for the monitored workspace(s), last 30 days, slimmed for downstream_impact. Tables that have since been dropped are left out. Refreshed every 15 minutes.' AS
WITH live AS (
  SELECT concat_ws('.', table_catalog, table_schema, table_name) AS full_name FROM system.information_schema.tables
)
SELECT l.source_table_full_name AS src, l.target_table_full_name AS tgt, l.entity_type,
       coalesce(l.entity_metadata.job_info.job_id, l.entity_metadata.dlt_pipeline_info.dlt_pipeline_id,
                l.entity_metadata.dashboard_id, l.entity_metadata.genie_space_id, l.entity_id) AS entity,
       max(l.event_time) AS event_time
FROM system.access.table_lineage l
LEFT SEMI JOIN live ON live.full_name = coalesce(l.target_table_full_name, l.source_table_full_name)
WHERE l.workspace_id IN (${workspace_ids}) AND l.event_date >= current_date() - 30
GROUP BY ALL;
