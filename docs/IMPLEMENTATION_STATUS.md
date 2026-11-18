# Implementation status

This branch is a functional initial release with a working browser-to-worker analytical path. It covers the foundation, workspace access, dataset imports and cleaning, SQL analytics, LangGraph role workflows, charts, reports, and recurring local jobs.

| Area | Implemented | Remaining scope |
| --- | --- | --- |
| Roles | Twelve registered roles with one fixture-backed domain workflow each | Full specialist capability catalog, domain policy validation, and richer interpretation |
| Planning | Local aggregate planning, one optional OpenAI or Gemini plan, typed routing, trace, PostgreSQL checkpoints, cancellation and retry | Arbitrary multi-intent planning, full conversational memory, interactive approval inside graph execution |
| Data | CSV, XLSX, JSON, Parquet, SQLite and DuckDB import, named administrator PostgreSQL sources, profiling, and immutable versions | MySQL, REST, Google Sheets, warehouse and direct cloud import connectors, plus ingestion isolation and retention |
| Analysis | Read-only SQL, optional two-source joins, basic profiling, outliers and ratios, Welch test, Holt forecasting, regression and classification comparisons | Advanced pipelines, semantic metric catalogs, attribution, richer experimentation and model validation |
| Charts and reports | Persisted chart dashboards, local filters, authorized sharing, CSV and Plotly dashboard exports, six report formats | Cross-panel filtering, public shares, and broader layouts and dashboard export targets |
| Research | Opt-in Brave search with timestamped candidate evidence and source assessments | Full-text retrieval, claim cross-checking, and systematic conflict detection |
| Operations | Docker Compose, Celery, recurring approvals, worker recovery, database migrations, structured logging, API metrics and CI | Scaled production operations, privacy review, independent security audit, load testing, and full worker metrics aggregation |

The deployable Compose stack is intended for evaluation and controlled internal testing. Review TLS, ingress limits, backup and retention requirements, and isolation of uploaded-file parsing before a public rollout. Live provider and external storage checks require service credentials. See [Testing](TESTING.md) for local verification commands.

## Verification

- Backend suite with 30 passing tests, including tenant isolation, all twelve role calculations, SQL restrictions, dataset versions, forecasts, and all six report formats.
- Two passing Playwright scenarios cover the main desktop workflow and mobile navigation. The production Next.js build and TypeScript check passed. GitHub Actions verified both tests against the full Compose stack.
- A PostgreSQL and Redis integration run verified Alembic startup, Celery worker readiness, queued imports and reports, scheduled dispatch, and recovery from a durable LangGraph checkpoint.
- npm and Python dependency audits reported zero known vulnerabilities in the audited runtime dependency sets.
- OpenAI, Gemini, and Brave Search contracts were exercised with mocked responses. Live providers, SMTP delivery, and S3 require deployment credentials for live verification.

## Production-readiness branch

| Requirement | Status | Evidence |
| --- | --- | --- |
| Audit all 12 roles and add the first four specialist methods | Implemented, verification pending | [Role inventory, fields, formulas, and assumptions](SPECIALIST_ANALYSIS.md). |
| Specialist expansion across the other nine roles | Implemented, verification pending | [Known-answer fixtures cover one additional calculation per role](SPECIALIST_ANALYSIS.md). Broader qualitative analysis and forecasting remain open. |
| Durable multi-step workflows, inspection, approval, retry, and cancellation | Implemented, verification pending | Bounded plans run validated analytical steps. The next checkpoint, completed outputs, and approval index persist in the application database. |
| Read full research sources and cite conflicting or insufficient evidence | Implemented, verification pending | Bounded HTTPS HTML/text retrieval and per-claim percentage checks. Broader claim types and live Brave verification remain open. |
| Google Sheets, MySQL, and REST connectors | Implemented, verification pending | Named administrator-managed sources use the existing immutable import pipeline. |
| Additional warehouse connectors | Still open | The baseline report names warehouses as a category and does not specify a vendor, authentication method, or import contract. |
| Dashboard-wide filters and revocable sharing | Implemented, verification pending | Snapshot-only public endpoints with opt-in management and hashed tokens. |
| PostgreSQL and local artifact backup and restore | Implemented, verification pending | [Recovery runbook and disposable-deployment drill](OPERATIONS.md). |
| Retention, queue depth, worker health, failure and retry exhaustion visibility | Implemented, verification pending | Operator retention policy, Compose worker health, persisted job counts, and Redis broker depth. |
| Production load and defensive checks | Implemented, verification pending | GitHub Actions runs the isolated synthetic deployment exercise. |
| Linux npm, Compose and browser regression checks | Verification pending | GitHub Actions verifies fresh builds and installations. |
| Windows and available macOS npm checks | Verification pending | GitHub Actions includes both hosts. macOS Monterey is blocked on a Monterey host. |
| Live OpenAI, Gemini, Brave, SMTP, and S3 | Blocked | Requires authorized service environments and credentials. Current provider HTTP fixtures are mocked. |
