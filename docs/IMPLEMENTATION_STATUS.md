# Implementation status

The production-readiness branch builds on the one-terminal npm baseline. The baseline inventory below records the scope at the time of that release. Current status and verification follow it.

| Area | Baseline capability | Baseline gap |
| --- | --- | --- |
| Roles | Twelve registered roles with one fixture-backed domain workflow each | Full specialist capability catalog, domain policy validation, and richer interpretation |
| Planning | Local aggregate planning, one optional OpenAI or Gemini plan, typed routing, trace, PostgreSQL checkpoints, cancellation and retry | Arbitrary multi-intent planning, full conversational memory, interactive approval inside graph execution |
| Data | CSV, XLSX, JSON, Parquet, SQLite and DuckDB import, named administrator PostgreSQL sources, profiling, and immutable versions | MySQL, REST, Google Sheets, warehouse and direct cloud import connectors, plus ingestion isolation and retention |
| Analysis | Read-only SQL, optional two-source joins, basic profiling, outliers and ratios, Welch test, Holt forecasting, regression and classification comparisons | Advanced pipelines, semantic metric catalogs, attribution, richer experimentation and model validation |
| Charts and reports | Persisted chart dashboards, local filters, authorized sharing, CSV and Plotly dashboard exports, six report formats | Cross-panel filtering, public shares, and broader layouts and dashboard export targets |
| Research | Opt-in Brave search with timestamped candidate evidence and source assessments | Full-text retrieval, claim cross-checking, and systematic conflict detection |
| Operations | Docker Compose, Celery, recurring approvals, worker recovery, database migrations, structured logging, API metrics and CI | Scaled production operations, privacy review, independent security audit, load testing, and full worker metrics aggregation |

The deployable Compose stack is intended for evaluation and controlled internal testing. Review TLS, ingress limits, backup and retention requirements, and isolation of uploaded-file parsing before a public rollout. Live provider and external storage checks require service credentials. See [Testing](TESTING.md) for local verification commands.

## Baseline verification

- Backend suite with 30 passing tests, including tenant isolation, all twelve role calculations, SQL restrictions, dataset versions, forecasts, and all six report formats.
- Two passing Playwright scenarios cover the main desktop workflow and mobile navigation. The production Next.js build and TypeScript check passed. GitHub Actions verified both tests against the full Compose stack.
- A PostgreSQL and Redis integration run verified Alembic startup, Celery worker readiness, queued imports and reports, scheduled dispatch, and recovery from a durable LangGraph checkpoint.
- npm and Python dependency audits reported zero known vulnerabilities in the audited runtime dependency sets.
- OpenAI, Gemini, and Brave Search contracts were exercised with mocked responses. Live providers, SMTP delivery, and S3 require deployment credentials for live verification.

## Production-readiness branch

| Requirement | Status | Evidence |
| --- | --- | --- |
| All 12 specialist roles | Implemented and verified | Known-answer fixtures cover the requested four methods and nine additional methods. [Formulas, units, and missing-data handling](SPECIALIST_ANALYSIS.md). |
| Multi-step workflows with preserved context, approvals, inspection, retry, and cancellation | Implemented and verified | Explicit workflows and opt-in planning for requests ordered with “then” use typed inputs and per-step access checks. Tests cover deferred and duplicate approvals, cancellation, retry, and cross-project inputs. |
| Research source reading and per-claim evidence | Implemented and verified with fixtures | Bounded HTTPS HTML and plain-text reads. Exact-subject percentage checks report citations, disagreement and insufficient evidence. Brave discovery, source fetch results, and suitability of matches were tested with fixtures. |
| Google Sheets and REST connectors | Implemented and verified with mocks | Imports pass through the shared immutable dataset pipeline. [Configuration and supported response shapes](CONNECTORS.md). |
| MySQL connector | Implemented, live verification pending | Requires a reachable test MySQL database with read-only credentials and an agreed fixture table. |
| Additional warehouses and direct cloud import connectors | Still open | The project specifies no concrete warehouse vendor, credentials, or import contract. Direct import from object storage is separate from the platform's S3 artifact storage. |
| Dashboard-wide filters and revocable read-only sharing | Implemented and verified | Playwright filters charts with the same grouping field and opens and revokes a dashboard in a signed-out browser. API tests cover token rotation, tenant scope, and removal of project and analysis metadata. |
| PostgreSQL and local artifact backup and restore | Implemented and verified | Fresh Compose project restored an account, project, analysis, dashboard, two dataset versions and a report. Exported bytes matched their original checksums. [Compose job](https://github.com/Mole1614x/multi-role-analyst-ai/actions/runs/44335964579/job/134912643187). |
| Retention, queue depth, worker health, and retry exhaustion | Implemented and verified | Tests cover persisted retry-exhaustion status and metrics. Compose workers answered their health probes and reported Redis queue depth. [Operations runbook](OPERATIONS.md). |
| Production load and defensive checks | Implemented and verified | Compose baseline drill ran 16 analytical jobs using four concurrent clients, all correct, in 1.11 seconds with p95 0.56 seconds. It checked cross-tenant project, dataset and report access, upload limit, and read-only SQL. [Compose job](https://github.com/Mole1614x/multi-role-analyst-ai/actions/runs/44335964579/job/134912643187). |
| Linux npm startup, tests, lint, and build | Implemented and verified | Fresh-checkout npm CI passed. The interactive launch also migrated a populated SQLite copy with account, dataset, dashboard, job and report records. Restart preserved all rows and exports, and Ctrl+C released both ports twice. [Linux job](https://github.com/Mole1614x/multi-role-analyst-ai/actions/runs/44335964579/job/134912643353). |
| Current macOS npm setup and browser tests | Implemented and verified | GitHub's ARM64 runner reported macOS 26.7.2. [macOS job](https://github.com/Mole1614x/multi-role-analyst-ai/actions/runs/44335964579/job/134912643155). |
| Windows npm setup and browser tests | Implemented, verification pending | Prior run passed install, setup, lint and build and exposed an open SQLite import handle in tests. The code now explicitly closes the connection and releases the test connection pool. |
| macOS Monterey | Blocked | Requires a Monterey host with Python 3.11–3.13 and Node.js 22 LTS. The hosted macOS job exercises a newer release. |

### Live integrations

| Integration | Status | Prerequisite |
| --- | --- | --- |
| OpenAI | Blocked, HTTP contract mocked | Authorized OpenAI project API key and billing access for an enabled model. Set `ANALYST_LLM_PROVIDER=openai` and `ANALYST_LLM_API_KEY`. |
| Gemini | Blocked, HTTP contract mocked | Authorized Google Gemini API key and quota for an enabled model. Set `ANALYST_LLM_PROVIDER=gemini` and `ANALYST_LLM_API_KEY`. |
| Brave Search | Blocked, HTTP contract mocked | Valid Brave Search API subscription token in `ANALYST_RESEARCH_API_KEY` and outbound HTTPS availability for the selected public sources. |
| SMTP | Blocked, transport mocked | Reachable SMTP STARTTLS server, configured sender, test recipient and authorized credentials if required. Set the corresponding `ANALYST_SMTP_*` variables. |
| S3 | Blocked, object transport stubbed | Test bucket and IAM credentials permitting artifact put, get and delete. Configure `ANALYST_S3_BUCKET`, AWS credentials and region, and `ANALYST_S3_ENDPOINT` if applicable. A live bucket recovery drill also requires a versioned destination and backup permissions. |
| Google Sheets | Blocked, HTTP contract mocked | A known public sheet and API key, or a test sheet readable by an OAuth token. |
| REST | Blocked, HTTP contract mocked | A named HTTPS fixture endpoint that serves a known bounded JSON response and its bearer credential if needed. |

Broader qualitative specialist methods, unrestricted multi-intent decomposition, non-percentage claim verification, recomputation of dashboard metrics for heterogeneous filters, and sustained mixed load and independent security review remain open.
