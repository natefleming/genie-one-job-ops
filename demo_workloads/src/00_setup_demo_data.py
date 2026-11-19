# Databricks notebook source
# MAGIC %md
# MAGIC # Demo — setup
# MAGIC Creates the demo schema, failure flags (all off), reference tables and the landing volume.

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {fq} COMMENT 'Demo workloads for the Job Ops POC (synthetic data)'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {fq}.landing COMMENT 'Where the (simulated) MuleSoft inventory flow drops files'")

spark.sql(f"CREATE TABLE IF NOT EXISTS {fq}.demo_flags (flag STRING, enabled BOOLEAN, description STRING)")
spark.sql(f"""MERGE INTO {fq}.demo_flags t USING (SELECT * FROM VALUES
  ('region_west_targets_missing', false, 'West region sales targets table is missing -> nested for-each task fails'),
  ('pos_bad_amounts', false, 'Store POS feed sends N/A in the amount column -> silver build fails on CAST'),
  ('mulesoft_feed_missing', false, 'MuleSoft inventory flow did not drop the nightly file'),
  ('bigquery_outage', false, 'BigQuery connection fails -> web events table stops receiving data'),
  ('orders_negative_totals', false, 'Order feed contains negative totals -> pipeline expectation fails')
  AS v(flag, enabled, description)) s ON t.flag = s.flag
WHEN NOT MATCHED THEN INSERT *""")

spark.sql(f"""CREATE OR REPLACE TABLE {fq}.stores AS
SELECT id AS store_id, concat('Store ', lpad(id, 4, '0')) AS store_name,
       element_at(array('northeast','southeast','central','west'), CAST(id % 4 AS INT) + 1) AS region
FROM range(1, 401)""")

for region in ["northeast", "southeast", "central", "west"]:
    spark.sql(f"""CREATE TABLE IF NOT EXISTS {fq}.store_targets_{region} AS
      SELECT store_id, CAST(15000 + rand() * 10000 AS DECIMAL(12,2)) AS daily_target
      FROM {fq}.stores WHERE region = '{region}'""")

spark.sql(f"""CREATE TABLE IF NOT EXISTS {fq}.orders_source (
  order_id BIGINT, store_id BIGINT, order_ts TIMESTAMP, order_total DECIMAL(12,2), channel STRING)""")
print("demo setup complete")
