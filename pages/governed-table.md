# Governed vs. ungoverned table

Domain: {{domain}}

Synonyms:
- governed table
- monitored table
- ungoverned table
- owned table

Description:
A governed table has an owner and is watched, ideally with data quality monitoring; an ungoverned table has neither, so problems are found by the people using it.

## Definition
- **Governed:** carries an owner or domain tag, and ideally has data quality monitoring turned on, so freshness and completeness are checked automatically.
- **Ungoverned:** no owner and no monitoring.

## How to check
- Tags: `<catalog>.information_schema.table_tags`
- Monitoring results: `system.data_quality_monitoring.table_results` (needs an admin grant)

## Recommendation
Turn on data quality monitoring for the gold tables that feed dashboards and Genie agents.

## Sources
- Genie One Job Ops project (pages/governed-table.md)
