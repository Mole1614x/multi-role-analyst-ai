# Security

Passwords use Argon2id. Expiring session and reset tokens are stored as hashes. Browser mutation requests check origin and fetch metadata. Redis-backed quotas apply in Compose. Secure cookies are available with HTTPS. Set deployment administrators by account UUID to avoid granting access through an unverified email address.

Projects and uploads are scoped by workspace memberships. Viewers can inspect existing resources, including original data. Owners manage workspace access. Dataset and report downloads resolve IDs only after authorization. Files use generated object keys. Spreadsheet values are protected against formula evaluation through export-specific escaping and writer settings.

DuckDB queries use a single parsed SELECT or set operation over registered tables, a function allowlist, disabled external filesystem and extension access, a memory ceiling, and a time budget. Imports bound input dimensions and decompression. Protect public deployments further with ingress request limits, per-deployment egress controls, backups, and a review of binary parser exposure. Employee data should be aggregated before import. Workspace permissions govern original personnel data. HR-mode results use an aggregate threshold.

Provider calls require explicit user approval. Model planning can send a user prompt and column names/types. Brave Search receives the approved research question. Neither integration includes full datasets in its payload. Keep secrets in an operator-controlled secret store and use read-only, least-privileged credentials for PostgreSQL connectors.

Development uses local SQLite and omits Redis-backed rate limiting by default. Before exposing the stack publicly, configure TLS and secure cookies, restrict access to the API and administrative ports, and verify backup, retention, and abuse-monitoring procedures.
