# Databricks notebook source
# MAGIC %md # Exec Sales Report · morning regional sales vs. target for the leadership dashboard

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
spark.sql(f"""CREATE OR REPLACE TABLE {fq}.rpt_exec_sales AS
SELECT region, sale_date, sales, avg_pct_of_target, current_timestamp() AS built_at
FROM {fq}.gold_sales_summary""")
