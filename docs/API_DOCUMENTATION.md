# API documentation

Uvicorn serves interactive documentation at `/api/docs` and the machine-readable schema at `/api/openapi.json`. Every project route is scoped by `/api/projects/{project_id}`. Requests use the HttpOnly session cookie issued by registration or login. Browser writes require the configured origin.

| Resource | Operations |
| --- | --- |
| `/api/auth` | Register, sign in and out, fetch account, request or complete password reset |
| `/api/workspaces` | List memberships, manage access by account ID, view owner audit history |
| `/api/roles`, `/api/projects` | Discover roles, list or create projects, get and update a project |
| `/datasets`, `/versions/{id}` | Multipart imports, inspect versions, clean with preview, download Parquet |
| `/connectors` | Discover and import administrator-configured PostgreSQL sources |
| `/sql/draft`, `/sql` | Draft analytical SQL, execute and save results, inspect query history, export CSV |
| `/analyses`, `/jobs` | Submit, list, inspect, stream, cancel, and retry analysis, report, and import jobs |
| `/dashboards` | Save one or more charts, list snapshots, export chart data |
| `/reports`, `/artifacts/{id}` | Queue a format conversion and download the finished artifact |
| `/schedules` | Create approved recurring jobs, inspect or stop schedules |
| `/api/admin`, `/api/health/*` | Administrator deployment counts, liveness and readiness |

For a job response, use `GET /jobs/{id}` until `status` is `completed`, `failed`, or `canceled`. Event streams at `GET /jobs/{id}/events` send JSON snapshots with status and trace. Reconnects can read the current state with an ordinary GET.

Automatic local queries understand aggregation of named numeric fields, row counts, and grouping. One optional join can use `dataset_b`; the primary table is `dataset`. The canonical SQL and source version IDs are recorded. Select a stored analytical result for dashboard and report creation.

Validation errors use a `detail` field. A project or subordinate resource outside the current tenant returns 404. Insufficient permissions for a known resource return 403.
