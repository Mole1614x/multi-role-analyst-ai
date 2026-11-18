# Multi-Role AI Analyst Platform

Analyst Workspace turns tabular data into repeatable analyses, dashboards, and reports. Create a project, choose from 12 analyst roles, upload a dataset, and ask a question against a specific dataset version. The default setup runs on your machine using SQLite and a local background worker. Data cleaning, SQL, specialist calculations, charts, and reports work without provider credentials.

[Quick start](#quick-start) · [Try the workspace](#try-the-workspace) · [Analyst roles](#analyst-roles) · [Workflows](#workflows) · [Configuration](#configuration) · [Testing](#testing) · [Deployment](#deployment) · [Documentation](#documentation)

## Quick start

Install Git, Python **3.11–3.13**, and Node.js **22 LTS (22.13 or newer)**. Use the latest compatible Node.js 22 patch on macOS Monterey.

```bash
git clone --branch fix/complete-production-readiness https://github.com/Mole1614x/multi-role-analyst-ai.git
cd multi-role-analyst-ai
npm install
npm run setup
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and create an account. The backend serves [interactive API docs](http://127.0.0.1:8000/docs). Press **Ctrl+C** in the terminal to stop both servers.

`npm install` runs setup automatically. `npm run setup` rechecks dependencies and applies SQLite migrations. The launcher creates `backend/.venv` and `.env.development.local` when needed. The default database is `backend/data/analyst_dev.db`, and dataset and report files are in `backend/data/storage/`. Back up both paths together before moving or upgrading an existing local workspace. [Development setup](docs/DEVELOPMENT_SETUP.md)

## Try the workspace

Save this sample as `sales-test.csv`.

```csv
date,region,revenue,expenses
2025-01-01,North,100,60
2025-01-02,South,70,40
2025-01-03,North,50,30
2025-01-03,North,50,30
```

1. Create a project and select **Data Analyst**, **Financial Analyst**, and **Sales Analyst**.
2. In **Datasets**, upload `sales-test.csv`. The profile should show **4 rows** and **1 duplicate**.
3. In **Cleaning studio**, preview removing duplicates and save the result. Version 2 should have **3 rows**. Version 1 remains available.
4. In **AI analysts**, select version 2 and run `Total revenue by region`. Expect **North = 150**, **South = 70**, **total revenue = 220**, and **profit = 90**.
5. Save the chart as a dashboard. In **Dashboards**, use **Download PNG** for an image of the saved chart. Filter for `South` and open **View chart data** to check the displayed result.
6. In **Reports**, select the completed analysis and generate a CSV. Check that it contains the regional values `North,150` and `South,70`.

## Analyst roles

Choose the roles available to a project, then select the roles to run in **Analysts for this request**. Each role uses the same versioned data and execution engine. General requests can return the default calculation. To run a specialist method, include its prompt phrase and provide the columns shown.

| Analyst | Default calculation | Specialist prompt and input columns |
| --- | --- | --- |
| **Data Analyst** | Descriptive statistics for a numeric column | `Pearson correlation` with matched numeric pairs in `x` and `y` |
| **Business Analyst** | Actual minus target using `actual` and `target` | `Business case` with `expected_benefit` and `implementation_cost` |
| **Market Research Analyst** | Segment share using `segment_size` and `market_size` | `Market sizing` for TAM, SAM, and SOM using `total_accounts`, `serviceable_accounts`, `obtainable_accounts`, and `annual_revenue_per_account` |
| **Financial Analyst** | Profit and margin using `revenue` and `expenses` | `Budget variance` with `actual` and `budget`. `Cash flow` with `cash_inflow` and `cash_outflow` |
| **Marketing Analyst** | Return on ad spend using `attributed_revenue` and `ad_spend` | `Last-touch attribution` with `conversion_id`, `channel`, `touch_at`, and `conversion_value` |
| **Sales Analyst** | Total booked `revenue` | `Weighted pipeline` with `deal_amount` and `probability` |
| **Product Analyst** | Retention using `retained` and `eligible` | `Cohort churn` with `cohort`, `eligible`, and `retained` |
| **HR Analyst** | Aggregate turnover using `departures` and `average_headcount`, with at least 10 complete rows | `Hiring funnel` with aggregate `applicants`, `interviewed`, and `hired` counts. Small stage and drop-off counts are suppressed |
| **Operations Analyst** | Fulfillment rate using `fulfilled` and `ordered` | `Inventory coverage` with `average_inventory` and `daily_demand` |
| **Business Intelligence Analyst** | Completeness, missing cells, and duplicate rows for a tabular dataset | `Key uniqueness` with `record_key` |
| **Risk Analyst** | Interquartile-range outlier count for a numeric column | `Expected loss` with `impact` and `probability` |
| **Investment Analyst** | Compounded return and observed volatility using decimal `period_return` | `Maximum drawdown` with chronologically ordered decimal `period_return` |

Analyses show unavailable findings when inputs are missing and surface assumptions about units, observation windows, and data quality. General analysis requests that include HR return aggregate HR findings only. Market sizing depends on supplied assumptions, and attribution assigns credit based on recorded touches. [Role defaults and policies](docs/ANALYST_ROLES.md) · [Specialist formulas and input rules](docs/SPECIALIST_ANALYSIS.md)

## Workflows

| Workspace | What you can do |
| --- | --- |
| **Datasets and Cleaning studio** | Import CSV, XLSX, JSON, Parquet, SQLite, and DuckDB. Inspect profiles and previews, then save transformations as new versions. Deployment admins can configure named PostgreSQL, MySQL, Google Sheets, and HTTPS REST sources. |
| **AI analysts and SQL studio** | Run specialist calculations or draft and execute read-only DuckDB queries. SQL studio can query across two selected dataset versions and export results as CSV. |
| **Forecasting & models** | Run a time-series forecast, evaluate a regression or classification model, or compare the means of two groups. Forecasts and model results include holdout evaluation. |
| **Research** | Discover public sources through Brave Search with approval. Provide a claim subject and percentage to check readable passages for agreement, conflicting values, or insufficient evidence. Results include citations and retrieval dates. |
| **Visualization builder and Dashboards** | Build charts and save single- or multi-chart dashboards. Apply a shared filter to charts with the same grouping field. Create and revoke read-only public links. Download a PNG image of the saved dashboard, CSV data, or a Plotly JSON specification. |
| **Reports** | Generate PDF, XLSX, PPTX, CSV, Markdown, or HTML from a completed analysis. |
| **Analysis history and Execution & schedules** | Inspect job traces, reopen results, approve pending steps, cancel work, and retry failures. Recurring analyses use the Redis and Celery stack. |

### Run and resume an analyst workflow

In **AI analysts**, enter `Total revenue by region` and click **Add analysis step**. Enter `Average revenue by region` as step 2 and select **Require approval**. Run the workflow, inspect step 1, and click **Approve step** to continue. On version 2 of the sample, the averages are **North = 75** and **South = 70**.

You can also write requests separated by **then** and select **Plan requests separated by “then” and review before execution**. This drafts a plan of two to six steps. To use an earlier analysis as context for a new request, select it under **Follow up on**.

### How jobs run

The LangGraph supervisor records the selected roles and request type. The planner loads the chosen dataset version, records its transformations, and validates any SQL before execution. The graph routes the request to specialist calculations, forecasting, model evaluation, group comparison, chart building, or research. Later stages create the chart when applicable, summarize results, and validate the response.

Job results can include the executed SQL, calculation methods, limitations, and the source version and hash. Workflow progress, completed steps, and pending approvals are saved. In local development, a paused workflow can resume after a restart. Local jobs that were queued or running when the process stopped are marked failed and can be retried. PostgreSQL supports durable LangGraph checkpoints in the Compose deployment. [Agent orchestration](docs/AGENT_ARCHITECTURE.md) · [API reference](docs/API_DOCUMENTATION.md)

## Configuration

Edit `.env.development.local` for the npm launcher or `.env` for Docker Compose. Use the corresponding example file as a reference, and keep real credentials in your local environment or deployment secrets.

| Optional capability | Configuration |
| --- | --- |
| OpenAI or Gemini planning | Set `ANALYST_LLM_PROVIDER` to `openai` or `gemini` and supply `ANALYST_LLM_API_KEY`. Set `ANALYST_LLM_MODEL` to override the default model. An approved planning request sends the prompt and column names and types. Calculations run in the workspace. |
| Brave Search | Set `ANALYST_RESEARCH_API_KEY` and allow outbound HTTPS to the public sources. A user must approve sending each research query. |
| Database, Sheets, and REST imports | Add the operator to `ANALYST_ADMIN_USER_IDS` and configure named sources. Use read-only database credentials where applicable. |
| Password reset email | Set the `ANALYST_SMTP_*` variables for a STARTTLS server and sender. |
| S3-compatible object storage | Set `ANALYST_S3_BUCKET`, supply access credentials and a region, and set `ANALYST_S3_ENDPOINT` if needed. |

Workspaces have owner, editor, and viewer access levels. Public sharing is opt-in. Anyone with a valid dashboard link can view the shared chart data until the link is revoked or replaced. [Local settings](.env.development.example) · [Deployment settings](.env.example) · [Connector setup](docs/CONNECTORS.md) · [Security](docs/SECURITY.md)

## Testing

From the repository root, run these commands after setup.

```bash
npm run lint
npm test
npm run build
```

`npm test` runs pytest and Playwright with an isolated SQLite workspace and temporary servers. It installs Chromium when needed. Tests cover analyst calculations, access controls, read-only SQL, imports, workflow approvals, dashboard links, and report downloads. The implementation branch passed **66 backend tests and 3 browser tests**. GitHub Actions also verified Linux, Windows, hosted macOS, and a Compose backup and restore drill. macOS Monterey and live provider verification remain open. [Testing guide](docs/TESTING.md) · [Passing CI run](https://github.com/Mole1614x/multi-role-analyst-ai/actions/runs/44339197650) · [Implementation status](docs/IMPLEMENTATION_STATUS.md)

## Deployment

Install Docker Engine with Compose or Docker Desktop. If `.env` is absent, create it from the example.

```bash
if [ ! -e .env ]; then (umask 077; cp .env.example .env); fi
```

Set `POSTGRES_PASSWORD` in `.env` to a unique URL-safe password, then start the stack.

```bash
docker compose up --build --wait
docker compose ps
```

Compose runs Next.js, FastAPI, PostgreSQL, Redis, a Celery worker, and a scheduler. A migration job upgrades the database before the API starts. By default, the web app is at `http://localhost:3000` and the API is at `http://127.0.0.1:8000`. The API exposes readiness and metrics, and the worker has its own health check. Use the operations guide to back up PostgreSQL and the object store together, test restoration, and review configuration before exposing a deployment. [Deployment guide](docs/DEPLOYMENT.md) · [Backup, restore, and monitoring](docs/OPERATIONS.md) · [Native services setup](docs/LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md)

## Documentation

| Topic | Where to look |
| --- | --- |
| Application and storage design | [Architecture](docs/ARCHITECTURE.md) · [Database design](docs/DATABASE_DESIGN.md) |
| Agent execution and analytical methods | [Agent orchestration](docs/AGENT_ARCHITECTURE.md) · [Specialist formulas](docs/SPECIALIST_ANALYSIS.md) |
| Development and troubleshooting | [Development setup](docs/DEVELOPMENT_SETUP.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) |
| HTTP API | [API reference](docs/API_DOCUMENTATION.md) |
| Verification and open work | [Implementation status](docs/IMPLEMENTATION_STATUS.md) |
