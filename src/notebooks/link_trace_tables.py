# Databricks notebook source
# MAGIC %md
# MAGIC # Job Ops — store the app's MLflow traces in Unity Catalog
# MAGIC Links the bundle's MLflow experiment to `<catalog>.<schema>.job_ops_traces_otel_*` (Databricks Apps can't reach the
# MAGIC experiment's default trace storage) and lets the Job Ops app's service principal write to those tables.
# MAGIC Idempotent; safe to re-run.

# COMMAND ----------
# MAGIC %uv pip install "mlflow-skinny>=3.18"
# MAGIC %restart_python

# COMMAND ----------
dbutils.widgets.text("catalog", "retail_consumer_goods")
dbutils.widgets.text("schema", "job_ops")
dbutils.widgets.text("warehouse_id", "")
dbutils.widgets.text("experiment_id", "")
dbutils.widgets.text("app_service_principal", "", "Application id of the Job Ops app's service principal")
dbutils.widgets.text("schema_only_scope", "false", "true = touch nothing outside the schema: no catalog grant")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
warehouse_id = dbutils.widgets.get("warehouse_id")
experiment_id = dbutils.widgets.get("experiment_id")
app_sp = dbutils.widgets.get("app_service_principal")
schema_only_scope = dbutils.widgets.get("schema_only_scope").lower() == "true"
TABLE_PREFIX = "job_ops_traces"

# COMMAND ----------
import os

import mlflow
from mlflow.entities.trace_location import UnityCatalog

os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = warehouse_id
mlflow.set_tracking_uri("databricks")
exp = mlflow.set_experiment(experiment_id=experiment_id,
                            trace_location=UnityCatalog(catalog_name=catalog, schema_name=schema, table_prefix=TABLE_PREFIX))
print(f"experiment {exp.experiment_id} → {getattr(exp, 'trace_location', None)}")

# COMMAND ----------
# MAGIC %md ## Let the app's service principal write traces

# COMMAND ----------
fq = f"`{catalog}`.`{schema}`"
tables = [r.tableName for r in spark.sql(f"SHOW TABLES IN {fq} LIKE '{TABLE_PREFIX}_otel_*'").collect()]
if not tables:
    raise RuntimeError(f"No {TABLE_PREFIX}_otel_* tables in {catalog}.{schema} after linking the experiment")
if not schema_only_scope:
    spark.sql(f"GRANT USE CATALOG ON CATALOG `{catalog}` TO `{app_sp}`")
spark.sql(f"GRANT USE SCHEMA ON SCHEMA {fq} TO `{app_sp}`")
for t in tables:
    spark.sql(f"GRANT SELECT, MODIFY ON TABLE {fq}.`{t}` TO `{app_sp}`")
print(f"granted {app_sp} SELECT, MODIFY on {', '.join(tables)}")
