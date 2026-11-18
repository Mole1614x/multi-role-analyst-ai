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
