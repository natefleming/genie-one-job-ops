# Databricks notebook source
# MAGIC %md # Nightly Sales Load · refresh one region (runs once per region, for-each)

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
dbutils.widgets.text("region", "northeast")
region = dbutils.widgets.get("region")
spark.sql(f"""CREATE OR REPLACE TABLE {fq}.gold_region_sales_{region} AS
SELECT s.sale_date, s.store_id, sum(s.amount) AS sales, any_value(t.daily_target) AS target,
       sum(s.amount) / any_value(t.daily_target) AS pct_of_target
FROM {fq}.silver_sales s JOIN {fq}.store_targets_{region} t USING (store_id)
WHERE s.region = '{region}' GROUP BY ALL""")
