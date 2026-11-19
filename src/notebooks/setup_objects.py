# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — create the data layer
# MAGIC Creates the schema objects Genie One answers from: the failure taxonomy, base views over
# MAGIC `system.lakeflow` / `system.access`, the metric views and the SQL functions, then grants
# MAGIC read access to the ops group. Idempotent; safe to re-run. The 15-minute refresh job runs only
# MAGIC `02_snapshots.sql` (via `only_files`).
# MAGIC
# MAGIC The views are owned by whoever runs this job, so that identity needs `SELECT` on the
# MAGIC `system.lakeflow` and `system.access` schemas. Users in the ops group only need access to
# MAGIC this schema, not to the system tables.

# COMMAND ----------
dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("ops_group", "account users")
dbutils.widgets.text("zeroops_url", "{host}/jobs?o={workspace_id}")
dbutils.widgets.text("workspace_ids", "", "Workspaces to monitor (comma-separated); empty = this workspace")
dbutils.widgets.text("bundle_root", "")
dbutils.widgets.text("only_files", "", "Run only these SQL files (comma-separated), e.g. 02_snapshots.sql for the 15-minute refresh")
dbutils.widgets.text("schema_only_scope", "false", "true = touch nothing outside the schema: never create it, no catalog grant")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
ops_group = dbutils.widgets.get("ops_group")
bundle_root = dbutils.widgets.get("bundle_root")
schema_only_scope: bool = dbutils.widgets.get("schema_only_scope").lower() == "true"
only_files: set[str] = {f.strip() for f in dbutils.widgets.get("only_files").split(",") if f.strip()}

# COMMAND ----------
import re
from pathlib import Path

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
host: str = w.config.host.rstrip("/")
workspace_id: str = str(w.get_workspace_id())
workspace_ids: list[str] = [x.strip() for x in dbutils.widgets.get("workspace_ids").split(",") if x.strip()] or [workspace_id]

subs: dict[str, str] = {
    "catalog": catalog,
    "schema": schema,
    "host": host,
    "workspace_ids": ", ".join(f"'{x}'" for x in workspace_ids),
    "zeroops_url": dbutils.widgets.get("zeroops_url").format(host=host, workspace_id=workspace_id),
}
print(subs)

# COMMAND ----------
def statements(path: Path) -> list[str]:
    """Render placeholders and split a SQL file on '-- @@' separator lines."""
    sql = path.read_text()
    for key, value in subs.items():
        sql = sql.replace("${" + key + "}", value)
    parts = re.split(r"^-- @@.*$", sql, flags=re.M)
    return [p.strip() for p in parts if any(line and not line.startswith("--") for line in p.strip().splitlines())]

if schema_only_scope:
    w.schemas.get(f"{catalog}.{schema}")  # fails if the assigned schema is missing; we never create it
else:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}` COMMENT 'Genie One Job Ops: metric views, functions, skills and MCP services'")

sql_dir = Path(bundle_root) / "src" / "sql"
for f in sorted(sql_dir.glob("*.sql")):
    if only_files and f.name not in only_files:
        continue
    for stmt in statements(f):
        print(f"{f.name}: {stmt.splitlines()[0][:100]}")
        spark.sql(stmt)

# COMMAND ----------
# MAGIC %md ## Mark automatic retries of for-each iterations
# MAGIC System tables don't record attempt numbers, so a retried iteration looks like a second failed input. The Jobs API
# MAGIC knows: iterations with `attempt_number > 0` are retries.

# COMMAND ----------
from databricks.sdk.errors import DatabricksError

if not only_files or "02_snapshots.sql" in only_files:
    fq = f"`{catalog}`.`{schema}`"
    parents = [r.parent_run_id for r in spark.sql(f"""
        SELECT DISTINCT parent_run_id FROM {fq}.task_runs
        WHERE is_nested AND is_failure AND start_time >= current_timestamp() - INTERVAL 7 DAYS""").collect()]
    retries: list[str] = []
    for parent in parents:
        try:
            iterations = w.jobs.get_run(int(parent)).iterations or []
        except DatabricksError as e:  # no access to that job, or the run is gone
            print(f"skipped {parent}: {e}")
            continue
        retries += [str(i.run_id) for i in iterations if (i.attempt_number or 0) > 0]
    if retries:
        spark.createDataFrame([(r,) for r in retries], "task_run_id STRING").createOrReplaceTempView("new_retries")
        spark.sql(f"""MERGE INTO {fq}.task_retries t USING (SELECT DISTINCT task_run_id FROM new_retries) n
                      ON t.task_run_id = n.task_run_id WHEN NOT MATCHED THEN INSERT *""")
        spark.sql(f"UPDATE {fq}.task_runs SET is_retry = true WHERE task_run_id IN (SELECT task_run_id FROM new_retries)")
    print(f"{len(retries)} retried iterations across {len(parents)} for-each runs")

# COMMAND ----------
# MAGIC %md ## Name the notebooks behind notebook workflow runs
# MAGIC Child runs started with `dbutils.notebook.run` only carry a notebook id (from lineage). The Jobs API knows the path;
# MAGIC look it up once per notebook, from that notebook's latest run.

# COMMAND ----------
if not only_files or "02_snapshots.sql" in only_files:
    unnamed = spark.sql(f"""
        SELECT notebook_id, max_by(run_id, start_time) AS run_id FROM {fq}.job_runs
        WHERE notebook_id IS NOT NULL AND notebook_id NOT IN (SELECT notebook_id FROM {fq}.notebook_paths)
        GROUP BY notebook_id""").collect()
    found: list[tuple[str, str]] = []
    for row in unnamed:
        try:
            tasks = w.jobs.get_run(int(row.run_id)).tasks or []
        except DatabricksError as e:  # no access to that run, or it's past the Jobs API's 60-day retention
            print(f"skipped notebook {row.notebook_id}: {e}")
            continue
        path = next((t.notebook_task.notebook_path for t in tasks if t.notebook_task), None)
        if path:
            found.append((row.notebook_id, path))
    if found:
        spark.createDataFrame(found, "notebook_id STRING, notebook_path STRING").createOrReplaceTempView("new_paths")
        spark.sql(f"""MERGE INTO {fq}.notebook_paths t USING new_paths n ON t.notebook_id = n.notebook_id
                      WHEN NOT MATCHED THEN INSERT *""")
    print(f"named {len(found)} of {len(unnamed)} new notebooks")

    # Latest error per failing notebook (7 days); only re-read when there's a newer failed run.
    latest = spark.sql(f"""
        SELECT r.notebook_id, max_by(r.run_id, r.start_time) AS run_id FROM {fq}.job_runs r
        WHERE r.notebook_id IS NOT NULL AND r.is_failure AND r.start_time >= current_timestamp() - INTERVAL 7 DAYS
        GROUP BY r.notebook_id
        HAVING max_by(r.run_id, r.start_time) NOT IN (SELECT run_id FROM {fq}.notebook_errors)""").collect()
    errors: list[tuple[str, str, str]] = []
    for row in latest:
        try:
            run = w.jobs.get_run(int(row.run_id))
            task_run_id = run.tasks[0].run_id if run.tasks else int(row.run_id)
            out = w.jobs.get_run_output(task_run_id)
        except DatabricksError as e:
            print(f"no error text for notebook {row.notebook_id}: {e}")
            continue
        if out.error:
            errors.append((row.notebook_id, row.run_id, out.error[:4000]))
    if errors:
        spark.createDataFrame(errors, "notebook_id STRING, run_id STRING, error STRING").createOrReplaceTempView("new_errors")
        spark.sql(f"""MERGE INTO {fq}.notebook_errors t USING new_errors n ON t.notebook_id = n.notebook_id
                      WHEN MATCHED THEN UPDATE SET t.run_id = n.run_id, t.error = n.error, t.captured_at = current_timestamp()
                      WHEN NOT MATCHED THEN INSERT (notebook_id, run_id, error, captured_at)
                                            VALUES (n.notebook_id, n.run_id, n.error, current_timestamp())""")
    print(f"captured errors for {len(errors)} of {len(latest)} failing notebooks")

# COMMAND ----------
# MAGIC %md ## Grants for the ops group

# COMMAND ----------
# In a schema we don't own, access is the schema owner's call (granting needs MANAGE); skip.
grants = [] if schema_only_scope else [
    f"GRANT USE CATALOG ON CATALOG `{catalog}` TO `{ops_group}`",
    f"GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA `{catalog}`.`{schema}` TO `{ops_group}`",
]
for grant in grants:
    print(grant)
    spark.sql(grant)

# COMMAND ----------
display(spark.sql(f"SELECT * FROM `{catalog}`.`{schema}`.failing_now(24)"))
