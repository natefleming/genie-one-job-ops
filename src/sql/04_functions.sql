-- Genie One Job Ops — UC SQL functions (trusted questions Genie can call).
-- Statements are separated by lines starting with "-- @@".

-- @@ What is broken right now?
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.failing_now(lookback_hours INT DEFAULT 24, include_notebook_runs BOOLEAN DEFAULT false)
RETURNS TABLE (
  job_id STRING, job_name STRING, job_owner STRING, last_run_id STRING, last_run_end TIMESTAMP,
  failure_category STRING, termination_code STRING, consecutive_failures BIGINT,
  failing_since TIMESTAMP, first_step STRING, run_url STRING, job_url STRING, is_notebook_run BOOLEAN
)
COMMENT 'Jobs whose most recent run in the lookback window failed, with how many times in a row it has failed, the plain-English failure category and a link to the run. Child notebook runs (dbutils.notebook.run) are left out unless include_notebook_runs: use failing_notebooks() for those.'
RETURN
  WITH recent AS (
    SELECT *, row_number() OVER (PARTITION BY job_id ORDER BY start_time DESC) AS rn
    FROM ${catalog}.${schema}.job_runs
    WHERE result_state IS NOT NULL
      AND start_time >= current_timestamp() - make_interval(0, 0, 0, 0, lookback_hours, 0, 0)
      AND (include_notebook_runs OR NOT is_notebook_run)
  ),
  last_ok AS (
    SELECT job_id, max(start_time) AS last_success
    FROM ${catalog}.${schema}.job_runs WHERE result_state = 'SUCCEEDED' GROUP BY job_id
  ),
  streak AS (
    SELECT r.job_id, count(*) AS consecutive_failures, min(r.start_time) AS failing_since
    FROM ${catalog}.${schema}.job_runs r LEFT JOIN last_ok o USING (job_id)
    WHERE r.is_failure AND r.start_time > coalesce(o.last_success, TIMESTAMP'1970-01-01')
    GROUP BY r.job_id
  )
  SELECT r.job_id, r.job_name, r.job_owner, r.run_id, r.end_time, r.failure_category, r.termination_code,
         s.consecutive_failures, s.failing_since, r.first_step, r.run_url, r.job_url, r.is_notebook_run
  FROM recent r JOIN streak s USING (job_id)
  WHERE r.rn = 1 AND r.is_failure
  ORDER BY s.consecutive_failures DESC, r.end_time DESC;

-- @@ Which child notebooks are failing?
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.failing_notebooks(lookback_hours INT DEFAULT 168)
RETURNS TABLE (
  notebook_key STRING, notebook_id STRING, notebook_path STRING, failed_runs BIGINT, succeeded_runs BIGINT,
  still_failing BOOLEAN, first_failure TIMESTAMP, last_failure TIMESTAMP, failure_category STRING,
  termination_code STRING, first_step STRING, last_failed_run_id STRING, last_failed_run_url STRING, last_error STRING
)
COMMENT 'Child notebook runs (started with dbutils.notebook.run from another notebook) that failed in the lookback window, one row per notebook. Each child run gets a throwaway job id, so counting them per job makes every failure look like a separate broken job; this groups them by the notebook that ran. still_failing = its most recent run failed; last_error = the latest captured error message. To re-run, re-run the job or notebook that calls it: child runs cannot be repaired on their own.'
RETURN
  WITH runs AS (
    SELECT *, coalesce(notebook_id, concat('job:', job_id)) AS notebook_key
    FROM ${catalog}.${schema}.job_runs
    WHERE is_notebook_run AND result_state IS NOT NULL
      AND start_time >= current_timestamp() - make_interval(0, 0, 0, 0, lookback_hours, 0, 0)
  )
  SELECT r.notebook_key, max(r.notebook_id), max(p.notebook_path),
         count_if(r.is_failure), count_if(r.result_state = 'SUCCEEDED'),
         max_by(r.is_failure, r.start_time),
         min(r.start_time) FILTER (WHERE r.is_failure), max(r.end_time) FILTER (WHERE r.is_failure),
         max_by(r.failure_category, r.end_time) FILTER (WHERE r.is_failure),
         max_by(r.termination_code, r.end_time) FILTER (WHERE r.is_failure),
         max_by(r.first_step, r.end_time) FILTER (WHERE r.is_failure),
         max_by(r.run_id, r.end_time) FILTER (WHERE r.is_failure),
         max_by(r.run_url, r.end_time) FILTER (WHERE r.is_failure),
         max(e.error)
  FROM runs r LEFT JOIN ${catalog}.${schema}.notebook_paths p USING (notebook_id)
  LEFT JOIN ${catalog}.${schema}.notebook_errors e USING (notebook_id)
  GROUP BY r.notebook_key
  HAVING count_if(r.is_failure) > 0
  ORDER BY 6 DESC, 4 DESC;

-- @@ Where do I go to fix it?
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.run_links(run_id_in STRING)
RETURNS TABLE (
  job_id STRING, run_id STRING, job_name STRING, result_state STRING, failure_category STRING,
  run_url STRING, job_url STRING, zeroops_url STRING, how_to_rerun STRING
)
COMMENT 'Links for a job run: the run page (where Repair run re-runs only the failed tasks), the job page, and the ZeroOps inbox for the root-cause investigation. Databricks checks the user''s own permissions when they open the link.'
RETURN
  SELECT job_id, run_id, job_name, result_state, failure_category, run_url, job_url,
         '${zeroops_url}' AS zeroops_url,
         'Open the run link and click "Repair run" to re-run only the failed tasks (and anything after them), or "Run now" on the job page for a fresh run. You need CAN MANAGE RUN on the job; Databricks checks this when you click.' AS how_to_rerun
  FROM ${catalog}.${schema}.job_runs
  WHERE run_id = run_id_in;

-- @@ Which tasks inside a run failed (including nested ones)?
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.run_tasks(run_id_in STRING)
RETURNS TABLE (
  task_key STRING, task_run_id STRING, parent_run_id STRING, is_nested BOOLEAN, result_state STRING,
  termination_code STRING, failure_category STRING, is_skipped_downstream BOOLEAN, is_retry BOOLEAN,
  start_time TIMESTAMP, end_time TIMESTAMP, task_run_url STRING
)
COMMENT 'Every task in a job run, in start order, with which ones failed, which were nested (for-each) and which were skipped because something upstream failed. is_retry marks an automatic retry of an earlier attempt of the same iteration: count failed iterations without the retries.'
RETURN
  SELECT task_key, task_run_id, parent_run_id, is_nested, result_state, termination_code, failure_category,
         is_skipped_downstream, is_retry, start_time, end_time, task_run_url
  FROM ${catalog}.${schema}.task_runs
  WHERE job_run_id = run_id_in
  ORDER BY start_time;

-- @@ Who is affected downstream?
CREATE OR REPLACE FUNCTION ${catalog}.${schema}.downstream_impact(job_id_in STRING)
RETURNS TABLE (
  hop INT, written_table STRING, impacted_asset STRING, asset_type STRING, last_seen TIMESTAMP
)
COMMENT 'Lineage impact of a job: the tables it writes (hop 0), then the tables, jobs, pipelines, dashboards and Genie agents that read those tables (hop 1) and the next layer of tables (hop 2). Based on the last 30 days of Unity Catalog lineage.'
RETURN
  WITH lin AS (
    SELECT src, tgt, entity_type, entity, event_time FROM ${catalog}.${schema}.table_lineage_30d
  ),
  written AS (
    SELECT DISTINCT tgt AS t FROM lin
    WHERE entity_type = 'JOB' AND entity = job_id_in AND tgt IS NOT NULL
  ),
  hop1 AS (
    SELECT w.t AS written_table,
           coalesce(l.tgt, concat(lower(l.entity_type), ':', l.entity)) AS impacted_asset,
           CASE WHEN l.tgt IS NOT NULL THEN 'TABLE' ELSE l.entity_type END AS asset_type,
           max(l.event_time) AS last_seen
    FROM written w JOIN lin l ON l.src = w.t
    WHERE NOT (l.entity_type = 'JOB' AND l.entity = job_id_in)
    GROUP BY ALL
  ),
  hop2 AS (
    SELECT h.written_table, l.tgt AS impacted_asset, 'TABLE' AS asset_type, max(l.event_time) AS last_seen
    FROM hop1 h JOIN lin l ON l.src = h.impacted_asset
    WHERE h.asset_type = 'TABLE' AND l.tgt IS NOT NULL
    GROUP BY ALL
  )
  SELECT 0 AS hop, t AS written_table, t AS impacted_asset, 'TABLE' AS asset_type, CAST(NULL AS TIMESTAMP) AS last_seen FROM written
  UNION ALL SELECT 1, * FROM hop1
  UNION ALL SELECT 2, * FROM hop2;
