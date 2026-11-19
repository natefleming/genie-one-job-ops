# Databricks notebook source
# MAGIC %md # Nightly Sales Load · publish the company sales summary

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
union = " UNION ALL ".join(
    f"SELECT '{r}' AS region, * FROM {fq}.gold_region_sales_{r}" for r in ["northeast", "southeast", "central", "west"])
spark.sql(f"""CREATE OR REPLACE TABLE {fq}.gold_sales_summary AS
SELECT region, sale_date, sum(sales) AS sales, avg(pct_of_target) AS avg_pct_of_target FROM ({union}) GROUP BY ALL""")
