# Databricks notebook source
# MAGIC %md
# MAGIC # Demo — chaos (break or heal)
# MAGIC `scenario=break` switches on the failure flags and starts the demo jobs; `scenario=heal`
# MAGIC switches them off and starts them again so they recover.

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
dbutils.widgets.text("scenario", "break")
dbutils.widgets.text("job_prefix", "Acme")
scenario = dbutils.widgets.get("scenario")
prefix = dbutils.widgets.get("job_prefix")
breaking = scenario == "break"

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
spark.sql(f"""UPDATE {fq}.demo_flags SET enabled = {str(breaking).lower()}
WHERE flag IN ('region_west_targets_missing', 'mulesoft_feed_missing', 'bigquery_outage', 'orders_negative_totals')""")

if breaking:
    spark.sql(f"DROP TABLE IF EXISTS {fq}.store_targets_west")
else:
    spark.sql(f"""CREATE TABLE IF NOT EXISTS {fq}.store_targets_west AS
      SELECT store_id, CAST(15000 + rand() * 10000 AS DECIMAL(12,2)) AS daily_target FROM {fq}.stores WHERE region = 'west'""")
    spark.sql(f"DELETE FROM {fq}.orders_source WHERE order_total < 0")

# Fresh orders for the pipeline (negative totals when breaking).
total = "-1 * round(rand() * 500, 2)" if breaking else "round(100 + rand() * 2900, 2)"
spark.sql(f"""INSERT INTO {fq}.orders_source
SELECT monotonically_increasing_id() + unix_timestamp() * 1000, CAST(1 + rand() * 399 AS BIGINT), current_timestamp(),
       CAST({total} AS DECIMAL(12,2)), element_at(array('store','web','phone'), CAST(rand()*3 AS INT)+1) FROM range(200)""")

for name in [f"{prefix} {n}" for n in ("Nightly Sales Load", "Inventory Sync (MuleSoft feed)", "Web Events Ingest (BigQuery)", "Customer Orders Refresh")]:
    job = next(iter(w.jobs.list(name=name)), None)
    if job:
        run = w.jobs.run_now(job.job_id)
        print(f"{scenario}: started {name} run {run.run_id}")
