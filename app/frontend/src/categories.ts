// Failure categories in a fixed order -> fixed categorical slots (validated palette; never re-ordered by rank).
export const CATEGORIES = ["Data Error", "Compute Error", "Access & Configuration", "Capacity & Limits", "Platform", "Other"] as const;

export const CATEGORY_HELP: Record<string, string> = {
  "Data Error": "The code ran and hit a data problem — bad, late or changed data, or a bug.",
  "Compute Error": "The machines running the job failed: crashes, out of memory, cloud capacity.",
  "Access & Configuration": "The job is set up wrong or lacks permission to something it needs.",
  "Capacity & Limits": "Too much running at once; the job was skipped or queued out.",
  Platform: "An unexpected error inside Databricks.",
  Other: "Anything that doesn't fit the categories above.",
};

export const slot = (category: string): number => {
  const i = CATEGORIES.indexOf(category as (typeof CATEGORIES)[number]);
  return (i < 0 ? CATEGORIES.length - 1 : i) + 1;
};
