-- Genie One Job Ops — UC metric views (the governed "numbers" Genie One answers from).
-- Statements are separated by lines starting with "-- @@".

-- @@ Job runs
CREATE OR REPLACE VIEW ${catalog}.${schema}.mv_job_runs
WITH METRICS LANGUAGE YAML
COMMENT 'Job run health: how many runs, how many failed, why, and how long it took to recover.' AS $$
version: 1.1
source: ${catalog}.${schema}.job_runs
dimensions:
  - name: run_date
    expr: CAST(start_time AS DATE)
    comment: Day the run started
  - name: run_hour
    expr: date_trunc('HOUR', start_time)
    comment: Hour the run started
  - name: job_name
    expr: job_name
  - name: job_id
    expr: job_id
  - name: job_owner
    expr: job_owner
    comment: Who the job runs as (or who created it)
  - name: failure_category
    expr: failure_category
    comment: Plain-English bucket - Data Error, Compute Error, Access & Configuration, Capacity & Limits, Platform, Cancelled, Success
  - name: termination_code
    expr: termination_code
  - name: result_state
    expr: result_state
  - name: trigger_type
    expr: trigger_type
    comment: What started the run (schedule, manual, file arrival, ...)
  - name: run_type
    expr: run_type
  - name: is_notebook_run
    expr: is_notebook_run
    comment: Child notebook run started with dbutils.notebook.run from another notebook; filter these out to count real jobs
  - name: is_failure
    expr: is_failure
measures:
  - name: total_runs
    expr: COUNT(1)
  - name: failed_runs
    expr: COUNT(1) FILTER (WHERE is_failure)
    comment: Runs that ended in an outcome someone needs to act on
  - name: failure_rate
    expr: COUNT(1) FILTER (WHERE is_failure) / NULLIF(COUNT(1) FILTER (WHERE result_state IS NOT NULL), 0)
    comment: Share of finished runs that failed
  - name: failing_jobs
    expr: COUNT(DISTINCT job_id) FILTER (WHERE is_failure)
  - name: unrecovered_failures
    expr: COUNT(1) FILTER (WHERE is_failure AND recovered_at IS NULL)
    comment: Failures with no successful run of the same job since
  - name: avg_hours_to_recover
    expr: AVG((unix_timestamp(recovered_at) - unix_timestamp(end_time)) / 3600.0) FILTER (WHERE is_failure AND recovered_at IS NOT NULL)
    comment: Mean time to recover (MTTR) in hours - from a failed run ending to the next successful run of the same job
  - name: avg_run_minutes
    expr: AVG(run_seconds) / 60.0
  - name: avg_queue_minutes
    expr: AVG(queue_seconds) / 60.0
$$;

-- @@ Task runs
CREATE OR REPLACE VIEW ${catalog}.${schema}.mv_task_runs
WITH METRICS LANGUAGE YAML
COMMENT 'Task-level health inside jobs, including nested for-each tasks and tasks skipped because something upstream failed.' AS $$
version: 1.1
source: ${catalog}.${schema}.task_runs
dimensions:
  - name: run_date
    expr: CAST(start_time AS DATE)
  - name: job_name
    expr: job_name
  - name: job_id
    expr: job_id
  - name: task_key
    expr: task_key
    comment: Task name inside the job
  - name: failure_category
    expr: failure_category
  - name: termination_code
    expr: termination_code
  - name: result_state
    expr: result_state
  - name: is_nested
    expr: is_nested
    comment: True for nested task runs, such as for-each iterations
  - name: is_retry
    expr: is_retry
    comment: True when this task run was an automatic retry of an earlier attempt
measures:
  - name: task_runs
    expr: COUNT(1)
  - name: failed_tasks
    expr: COUNT(1) FILTER (WHERE is_failure AND NOT is_retry)
    comment: Failed tasks, not counting automatic retries of the same task
  - name: skipped_downstream_tasks
    expr: COUNT(1) FILTER (WHERE is_skipped_downstream)
    comment: Tasks that did not run because an upstream task failed
  - name: task_failure_rate
    expr: COUNT(1) FILTER (WHERE is_failure AND NOT is_retry) / NULLIF(COUNT(1) FILTER (WHERE result_state IS NOT NULL AND NOT is_retry), 0)
  - name: avg_task_minutes
    expr: AVG(execution_seconds) / 60.0
$$;

-- @@ Pipeline updates
CREATE OR REPLACE VIEW ${catalog}.${schema}.mv_pipeline_updates
WITH METRICS LANGUAGE YAML
COMMENT 'Lakeflow pipeline update health.' AS $$
version: 1.1
source: ${catalog}.${schema}.pipeline_updates
dimensions:
  - name: update_date
    expr: CAST(start_time AS DATE)
  - name: pipeline_name
    expr: pipeline_name
  - name: pipeline_id
    expr: pipeline_id
  - name: pipeline_owner
    expr: pipeline_owner
  - name: result_state
    expr: result_state
  - name: update_type
    expr: update_type
  - name: trigger_type
    expr: trigger_type
measures:
  - name: updates
    expr: COUNT(1)
  - name: failed_updates
    expr: COUNT(1) FILTER (WHERE is_failure)
  - name: failing_pipelines
    expr: COUNT(DISTINCT pipeline_id) FILTER (WHERE is_failure)
  - name: pipeline_failure_rate
    expr: COUNT(1) FILTER (WHERE is_failure) / NULLIF(COUNT(1) FILTER (WHERE result_state IS NOT NULL), 0)
$$;

-- @@ Table freshness
CREATE OR REPLACE VIEW ${catalog}.${schema}.mv_table_freshness
WITH METRICS LANGUAGE YAML
COMMENT 'Which tables are still receiving data and which have gone quiet.' AS $$
version: 1.1
source: ${catalog}.${schema}.table_freshness
dimensions:
  - name: table_name
    expr: table_name
  - name: table_catalog
    expr: table_catalog
  - name: table_schema
    expr: table_schema
  - name: is_stale
    expr: is_stale
    comment: True when the table has gone more than twice its usual gap without a write ("receiving no data")
  - name: last_writer_type
    expr: last_writer_type
measures:
  - name: tables
    expr: COUNT(1)
  - name: stale_tables
    expr: COUNT(1) FILTER (WHERE is_stale)
  - name: max_hours_since_write
    expr: MAX(hours_since_write)
  - name: avg_typical_gap_hours
    expr: AVG(typical_gap_hours)
$$;
