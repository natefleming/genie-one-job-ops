# Databricks notebook source
# MAGIC %md # Nightly Sales Load · ingest store POS transactions (bronze)

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
bad = flag("pos_bad_amounts")
amount = "'N/A'" if bad else "CAST(round(200 + rand() * 2800, 2) AS STRING)"
spark.sql(f"""CREATE OR REPLACE TABLE {fq}.bronze_pos_sales AS
SELECT uuid() AS txn_id, s.store_id, current_date() - 1 AS sale_date,
       {amount} AS amount_raw, CAST(1 + rand() * 3 AS INT) AS units
FROM {fq}.stores s CROSS JOIN range(25)""")
print("bronze_pos_sales loaded", "(with N/A amounts)" if bad else "")
