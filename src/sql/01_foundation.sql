-- Genie One Job Ops — foundation objects.
-- Placeholders (${catalog}, ${schema}, ${workspace_id}, ${host}) are filled in by
-- src/notebooks/setup_objects.py. Statements are separated by lines starting with "-- @@".

-- @@ Failure taxonomy: plain-English buckets for Lakeflow termination codes
CREATE OR REPLACE TABLE ${catalog}.${schema}.failure_taxonomy (
  termination_code STRING COMMENT 'Lakeflow Jobs termination code',
  failure_category STRING COMMENT 'Plain-English bucket: Data Error, Compute Error, Access & Configuration, Capacity & Limits, Platform, Cancelled, Success',
  is_failure BOOLEAN COMMENT 'True when the outcome needs someone to act',
  meaning STRING COMMENT 'What the code means, in plain language',
  first_step STRING COMMENT 'Suggested first step for whoever is on call'
) COMMENT 'Maps job and task termination codes to the failure categories used by Genie One and the Job Ops app.';

-- @@
INSERT OVERWRITE ${catalog}.${schema}.failure_taxonomy VALUES
  ('SUCCESS', 'Success', false, 'The run finished normally.', 'Nothing to do.'),
  ('SUCCESS_WITH_FAILURES', 'Data Error', true, 'The run finished but one or more tasks failed and were allowed to.', 'Open the run and check which tasks failed.'),
  ('RUN_EXECUTION_ERROR', 'Data Error', true, 'The code ran and hit an error: bad or missing data, schema change, failed assertion, or a bug.', 'Read the error text on the failed task, then check upstream tables for recent changes.'),
  ('DRIVER_ERROR', 'Compute Error', true, 'The compute driver crashed or became unresponsive, often out of memory.', 'Check whether data volume spiked; consider a larger cluster or serverless.'),
  ('CLUSTER_ERROR', 'Compute Error', true, 'The cluster failed to start or was lost during the run.', 'Repair the run; if it repeats, check cluster policy and cloud capacity.'),
  ('CLOUD_FAILURE', 'Compute Error', true, 'The cloud provider could not supply machines or storage.', 'Repair the run; transient cloud issues usually clear on retry.'),
  ('LIBRARY_INSTALLATION_ERROR', 'Compute Error', true, 'A library the job needs could not be installed.', 'Check the library version and package repository access.'),
  ('INVALID_CLUSTER_REQUEST', 'Access & Configuration', true, 'The compute settings in the job are not valid.', 'Fix the cluster settings in the job definition.'),
  ('INVALID_RUN_CONFIGURATION', 'Access & Configuration', true, 'The job is set up incorrectly (bad parameter, missing notebook, wrong task settings).', 'Fix the job definition, then re-run.'),
  ('RESOURCE_NOT_FOUND', 'Access & Configuration', true, 'Something the job points at no longer exists (notebook, file, table, secret).', 'Restore or re-point the missing resource.'),
  ('UNAUTHORIZED_ERROR', 'Access & Configuration', true, 'The identity the job runs as lacks permission to something it needs.', 'Check the job run-as identity and grants on the objects it touches.'),
  ('STORAGE_ACCESS_ERROR', 'Access & Configuration', true, 'The job could not read or write cloud storage.', 'Check external location and storage credential permissions.'),
  ('REPOSITORY_CHECKOUT_FAILED', 'Access & Configuration', true, 'The job could not check out code from Git.', 'Check the Git credential and branch name.'),
  ('FEATURE_DISABLED', 'Access & Configuration', true, 'The job uses a feature that is not enabled in this workspace.', 'Ask a workspace admin to enable the feature.'),
  ('MAX_CONCURRENT_RUNS_EXCEEDED', 'Capacity & Limits', true, 'A previous run was still going, so this one was skipped.', 'Check why the previous run is slow; consider queueing.'),
  ('WORKSPACE_RUN_LIMIT_EXCEEDED', 'Capacity & Limits', true, 'The workspace hit its limit of concurrent runs.', 'Spread out schedules or ask an admin about limits.'),
  ('MAX_JOB_QUEUE_SIZE_EXCEEDED', 'Capacity & Limits', true, 'The job queue was full.', 'Spread out schedules.'),
  ('CLUSTER_REQUEST_LIMIT_EXCEEDED', 'Capacity & Limits', true, 'Too many compute requests at once.', 'Repair the run; stagger schedules.'),
  ('BUDGET_POLICY_LIMIT_EXCEEDED', 'Capacity & Limits', true, 'A budget policy blocked the run.', 'Talk to the budget owner.'),
  ('INTERNAL_ERROR', 'Platform', true, 'An unexpected error inside Databricks.', 'Repair the run; open a support ticket if it repeats.'),
  ('USER_CANCELED', 'Cancelled', false, 'Someone cancelled the run.', 'Confirm the cancel was intentional.'),
  ('USER_CANCELLED', 'Cancelled', false, 'Someone cancelled the run.', 'Confirm the cancel was intentional.'),
  ('CANCELED', 'Cancelled', false, 'The run was cancelled.', 'Confirm the cancel was intentional.'),
  ('CANCELLED', 'Cancelled', false, 'The run was cancelled.', 'Confirm the cancel was intentional.'),
  ('SKIPPED', 'Cancelled', false, 'The run or task was skipped.', 'Check the upstream task or schedule conditions.');

-- @@ For-each iterations that were automatic retries (system tables don't record attempts; the refresh reads the Jobs API)
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.task_retries (
  task_run_id STRING COMMENT 'Run id of a nested task run whose attempt_number > 0'
) COMMENT 'Nested task runs that were automatic retries of an earlier attempt, filled in by the 15-minute refresh from the Jobs API.';

-- @@ Notebook paths for notebook workflow runs (system tables only have the notebook id; the refresh reads the Jobs API)
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.notebook_paths (
  notebook_id STRING COMMENT 'Workspace notebook id, from Unity Catalog lineage',
  notebook_path STRING COMMENT 'Workspace path of the notebook'
) COMMENT 'Paths of notebooks run as notebook workflow runs (dbutils.notebook.run), filled in by the 15-minute refresh from the Jobs API.';

-- @@ Latest error of each failing child notebook (the app can't read child runs as the user; the refresh can)
CREATE TABLE IF NOT EXISTS ${catalog}.${schema}.notebook_errors (
  notebook_id STRING COMMENT 'Workspace notebook id',
  run_id STRING COMMENT 'The failed child run the error came from',
  error STRING COMMENT 'Error message of that run',
  captured_at TIMESTAMP COMMENT 'When the refresh read it'
) COMMENT 'Latest error message of each child notebook that failed in the last 7 days, filled in by the 15-minute refresh from the Jobs API.';

-- @@ Latest definition of each job (system.lakeflow.jobs keeps one row per change)
CREATE OR REPLACE VIEW ${catalog}.${schema}.v_jobs_current
COMMENT 'Current definition of every job in the monitored workspace(s).' AS
SELECT workspace_id, job_id, name AS job_name, tags,
       coalesce(run_as_user_name, creator_user_name) AS job_owner,
       creator_user_name, trigger_type, paused, description
FROM (
  SELECT *, row_number() OVER (PARTITION BY workspace_id, job_id ORDER BY change_time DESC) AS rn
  FROM system.lakeflow.jobs
  WHERE workspace_id IN (${workspace_ids})
)
WHERE rn = 1 AND delete_time IS NULL;

-- @@ One row per job run (job_run_timeline is split into hourly slices)
CREATE OR REPLACE VIEW ${catalog}.${schema}.v_job_runs
COMMENT 'One row per job run over the last 90 days with outcome, failure category, time-to-recover and links. is_notebook_run marks child notebook runs started with dbutils.notebook.run (they have no job page).' AS
WITH runs AS (
  SELECT workspace_id, job_id, run_id,
         min(period_start_time) AS start_time,
         max(period_end_time) AS end_time,
         max_by(result_state, period_end_time) FILTER (WHERE result_state IS NOT NULL) AS result_state,
         max_by(termination_code, period_end_time) FILTER (WHERE termination_code IS NOT NULL) AS termination_code,
         any_value(trigger_type) AS trigger_type,
         any_value(run_type) AS run_type,
         any_value(run_name) AS run_name,
         sum(coalesce(queue_duration_seconds, 0)) AS queue_seconds,
         sum(coalesce(execution_duration_seconds, 0)) AS execution_seconds,
         sum(coalesce(run_duration_seconds, 0)) AS run_seconds
  FROM system.lakeflow.job_run_timeline
  WHERE workspace_id IN (${workspace_ids})
    AND period_start_time >= current_timestamp() - INTERVAL 90 DAYS
  GROUP BY ALL
),
labeled AS (
  SELECT r.*,
         coalesce(j.job_name, r.run_name, concat('job ', r.job_id)) AS job_name,
         j.job_owner, j.tags AS job_tags,
         coalesce(t.failure_category,
                  CASE WHEN r.result_state IS NULL THEN 'Running' ELSE 'Other' END) AS failure_category,
         coalesce(t.is_failure, r.result_state IN ('FAILED', 'ERROR', 'TIMED_OUT')) AS is_failure,
         t.meaning AS failure_meaning,
         t.first_step
  FROM runs r
  LEFT JOIN ${catalog}.${schema}.v_jobs_current j USING (workspace_id, job_id)
  LEFT JOIN ${catalog}.${schema}.failure_taxonomy t ON t.termination_code = r.termination_code
)
SELECT *,
       -- When did this job next succeed after this failure?
       CASE WHEN is_failure THEN
         min(CASE WHEN result_state = 'SUCCEEDED' THEN end_time END)
           OVER (PARTITION BY workspace_id, job_id ORDER BY start_time
                 ROWS BETWEEN 1 FOLLOWING AND UNBOUNDED FOLLOWING)
       END AS recovered_at,
       -- Notebook workflow runs (dbutils.notebook.run from another notebook) get a throwaway job id with one run and
       -- no job page: Databricks opens them at #job/<id>/run/1.
       coalesce(run_type = 'WORKFLOW_RUN', false) AS is_notebook_run,
       CASE WHEN run_type = 'WORKFLOW_RUN' THEN concat('${host}/?o=', workspace_id, '#job/', job_id, '/run/1')
            ELSE concat('${host}/jobs/', job_id, '/runs/', run_id, '?o=', workspace_id) END AS run_url,
       CASE WHEN coalesce(run_type, '') <> 'WORKFLOW_RUN' THEN concat('${host}/jobs/', job_id, '?o=', workspace_id) END AS job_url
FROM labeled;

-- @@ One row per task run, including nested (for-each / run-job) tasks
CREATE OR REPLACE VIEW ${catalog}.${schema}.v_task_runs
COMMENT 'One row per task run over the last 90 days. is_nested marks task runs whose parent is another task (for-each iterations) rather than the job run.' AS
WITH tasks AS (
  SELECT workspace_id, job_id, job_run_id, run_id AS task_run_id, task_key, parent_run_id,
         min(period_start_time) AS start_time,
         max(period_end_time) AS end_time,
         max_by(result_state, period_end_time) FILTER (WHERE result_state IS NOT NULL) AS result_state,
         max_by(termination_code, period_end_time) FILTER (WHERE termination_code IS NOT NULL) AS termination_code,
         sum(coalesce(execution_duration_seconds, 0)) AS execution_seconds
  FROM system.lakeflow.job_task_run_timeline
  WHERE workspace_id IN (${workspace_ids})
    AND period_start_time >= current_timestamp() - INTERVAL 90 DAYS
  GROUP BY ALL
)
SELECT k.*,
       coalesce(j.job_name, concat('job ', k.job_id)) AS job_name,
       j.job_owner,
       coalesce(k.parent_run_id <> k.job_run_id, false) AS is_nested,
       coalesce(t.failure_category, CASE WHEN k.result_state IS NULL THEN 'Running' ELSE 'Other' END) AS failure_category,
       coalesce(t.is_failure, k.result_state IN ('FAILED', 'ERROR', 'TIMED_OUT')) AS is_failure,
       -- A task skipped because something upstream failed
       k.result_state IN ('SKIPPED', 'UPSTREAM_FAILED', 'EXCLUDED') AS is_skipped_downstream,
       concat('${host}/jobs/', k.job_id, '/runs/', k.task_run_id, '?o=', k.workspace_id) AS task_run_url
FROM tasks k
LEFT JOIN ${catalog}.${schema}.v_jobs_current j USING (workspace_id, job_id)
LEFT JOIN ${catalog}.${schema}.failure_taxonomy t ON t.termination_code = k.termination_code;

-- @@ One row per pipeline update
CREATE OR REPLACE VIEW ${catalog}.${schema}.v_pipeline_updates
COMMENT 'One row per Lakeflow pipeline update over the last 90 days.' AS
WITH p AS (
  SELECT workspace_id, pipeline_id, name AS pipeline_name, run_as AS pipeline_owner
  FROM (
    SELECT *, row_number() OVER (PARTITION BY workspace_id, pipeline_id ORDER BY change_time DESC) AS rn
    FROM system.lakeflow.pipelines WHERE workspace_id IN (${workspace_ids})
  ) WHERE rn = 1 AND delete_time IS NULL
),
u AS (
  SELECT workspace_id, pipeline_id, update_id,
         any_value(update_type) AS update_type,
         any_value(trigger_type) AS trigger_type,
         any_value(trigger_details.job_task.job_id) AS triggered_by_job_id,
         min(period_start_time) AS start_time,
         max(period_end_time) AS end_time,
         max_by(result_state, period_end_time) FILTER (WHERE result_state IS NOT NULL) AS result_state
  FROM system.lakeflow.pipeline_update_timeline
  WHERE workspace_id IN (${workspace_ids})
    AND period_start_time >= current_timestamp() - INTERVAL 90 DAYS
  GROUP BY ALL
)
SELECT u.*, coalesce(p.pipeline_name, concat('pipeline ', u.pipeline_id)) AS pipeline_name, p.pipeline_owner,
       u.result_state = 'FAILED' AS is_failure,
       concat('${host}/pipelines/', u.pipeline_id, '/updates/', u.update_id, '?o=', u.workspace_id) AS update_url
FROM u LEFT JOIN p USING (workspace_id, pipeline_id);

-- @@ Table freshness from lineage writes — "is this table still receiving data?"
CREATE OR REPLACE VIEW ${catalog}.${schema}.v_table_freshness
COMMENT 'Tables written on a recurring basis (3+ separate hours in the last 30 days) by jobs or pipelines, with last write time and typical gap between writes. A table is stale when the current gap is more than twice its usual gap.' AS
WITH writes AS (
  SELECT target_table_full_name AS table_name,
         target_table_catalog AS table_catalog, target_table_schema AS table_schema,
         date_trunc('HOUR', event_time) AS write_hour,
         any_value(coalesce(entity_metadata.job_info.job_id, entity_metadata.dlt_pipeline_info.dlt_pipeline_id)) AS writer_id,
         any_value(entity_type) AS writer_type
  FROM system.access.table_lineage
  WHERE workspace_id IN (${workspace_ids})
    AND event_date >= current_date() - 30
    AND target_table_full_name IS NOT NULL
    AND entity_type IN ('JOB', 'PIPELINE')
    -- Job Ops' own tables (written by its setup and refresh jobs) aren't data anyone is waiting for.
    AND target_table_full_name NOT IN (
      '${catalog}.${schema}.failure_taxonomy', '${catalog}.${schema}.job_runs', '${catalog}.${schema}.task_runs',
      '${catalog}.${schema}.pipeline_updates', '${catalog}.${schema}.table_freshness', '${catalog}.${schema}.table_lineage_30d')
  GROUP BY ALL
),
gaps AS (
  SELECT *, (unix_timestamp(write_hour) - unix_timestamp(lag(write_hour) OVER (PARTITION BY table_name ORDER BY write_hour))) / 3600.0 AS gap_hours
  FROM writes
)
SELECT table_name, table_catalog, table_schema,
       max(write_hour) AS last_write,
       count(*) AS write_hours_30d,
       percentile_approx(gap_hours, 0.5) AS typical_gap_hours,
       (unix_timestamp(current_timestamp()) - unix_timestamp(max(write_hour))) / 3600.0 AS hours_since_write,
       max_by(writer_id, write_hour) AS last_writer_id,
       max_by(writer_type, write_hour) AS last_writer_type,
       (unix_timestamp(current_timestamp()) - unix_timestamp(max(write_hour))) / 3600.0
         > greatest(2 * coalesce(percentile_approx(gap_hours, 0.5), 24), 2) AS is_stale
FROM gaps
GROUP BY ALL
HAVING count(*) >= 3;
