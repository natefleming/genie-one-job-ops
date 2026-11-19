---
name: resolve-and-rerun
description: Tell the user exactly how to resolve a failed Databricks job - the link to repair or re-run it and the link to its Genie ZeroOps investigation. Use when someone asks "how do I fix it", "re-run it", "restart the job", "repair the run", or "where do I go to fix this".
---

# Resolve and re-run

You do not re-run jobs yourself. You give the user the right link; Databricks checks their own permissions when they click it. This keeps every re-run on the user's own identity.

## Steps

1. Get the links for the failed run:
   ```sql
   SELECT * FROM {{catalog}}.{{schema}}.run_links('<run_id>')
   ```
2. Decide what to recommend:
   - The cause is fixed or was temporary (Compute Error, Capacity & Limits, Platform, or an upstream feed that is now healthy): **Repair run** from the run link. It re-runs only the failed tasks and the ones after them.
   - The cause is in the code or the data (Data Error, Access & Configuration): fix first. Send the user to **Genie ZeroOps** (zeroops_url) for the root cause and a proposed fix, then repair.
   - Upstream still broken (check `integration-status`): wait or contact the owning team; re-running now will fail again.

## How to answer

- Say what to do in one line, then give the links as clickable markdown:
  - [Open the failed run](run_url) → click **Repair run**
  - [Open in Genie ZeroOps](zeroops_url) for the root cause and suggested fix
  - [Open the job](job_url) → **Run now** for a completely fresh run
- Mention that they need "Can Manage Run" permission on the job, and who owns the job (job_owner from `{{catalog}}.{{schema}}.job_runs`) if they don't have it.
- Never say a job was re-run or fixed.
