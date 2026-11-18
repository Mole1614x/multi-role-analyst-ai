# Database design

Each account starts with an owned workspace. A workspace groups projects using memberships with owner, editor, or viewer access. Role registry identifiers in project records refer to role definitions shipped with the application.

| Tables | Purpose |
| --- | --- |
| `users`, `sessions`, `reset_tokens` | Authentication records, salted Argon2 password hashes, and hashed expiring opaque tokens |
| `workspaces`, `memberships`, `projects` | Tenant association, access, and project role assignments |
| `datasets`, `dataset_versions` | Source metadata and immutable Parquet references with profile, parent, and hash |
| `jobs` | Requested workflow, submitter, attempt, checkpoint generation, structured results, and traces |
| `queries` | Executed SQL and version-pinned result snapshots |
| `dashboards`, `artifacts` | Saved charts and report objects tied to successful analysis or generation jobs |
| `audit_log`, `schedules` | Mutating activity and approved recurring jobs |
| `checkpoints*`, `checkpoint_migrations` | Durable LangGraph storage provisioned with the official PostgreSQL saver |

Foreign keys enforce project and workspace relationships. Unique indexes cover membership pairs, dataset version numbers, artifact formats within a job, object keys, and tokens. Query patterns use project, workspace, dataset, or status indexes. Application queries enforce tenant authorization before resolving an object key or job result. PostgreSQL row-level security is a possible future layer.

Analysis requests and prompt history are stored as jobs. Role, chart, report, and consent details are represented in structured registry entries, job records, artifacts, or dashboard snapshots.
