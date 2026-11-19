# Databricks notebook source
# MAGIC %md # Web Events Ingest · hourly copy of the website's events from BigQuery
# MAGIC Demo stand-in: generates events locally. With the "bigquery_outage" flag on it fails the way a
# MAGIC federated BigQuery read does when the connection is down, and the table stops receiving data.

# COMMAND ----------
# MAGIC %run ./_common

# COMMAND ----------
if flag("bigquery_outage"):
    raise ConnectionError(
        "[REMOTE_FUNCTION_HTTP_FAILED_ERROR] BigQuery read failed for `acme-digital.web_analytics.events`: "
        "connection timed out after 300s (bigquerystorage.googleapis.com:443). Check the GCP service account "
        "and the BigQuery connection.")

spark.sql(f"CREATE TABLE IF NOT EXISTS {fq}.bronze_web_events (event_id STRING, event_ts TIMESTAMP, page STRING, session_id STRING)")
spark.sql(f"""INSERT INTO {fq}.bronze_web_events
SELECT uuid(), current_timestamp() - make_interval(0,0,0,0,0, CAST(rand()*59 AS INT), 0),
       element_at(array('/products','/product-quiz','/stores','/checkout','/accessories'), CAST(rand()*5 AS INT)+1),
       uuid() FROM range(500)""")
