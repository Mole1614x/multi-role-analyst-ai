# Analyst Workspace

Analyst Workspace is a multi-role analytics application. It imports versioned datasets, runs checked DuckDB queries and specialist calculations, and saves charts, dashboards, and reports with the underlying evidence. The core workflow runs locally without a model API key.

## Option A — Run with Docker

Install Docker Engine and the Compose plugin, or Docker Desktop on macOS.

```bash
if [ ! -e .env ]; then (umask 077; cp .env.example .env); fi
```

Set `POSTGRES_PASSWORD` in `.env` to a unique URL-safe password. Then start the stack.

```bash
docker compose up --build --wait
```

Open [Analyst Workspace](http://localhost:3000), register an account, and create a project. The API is also available on loopback at [FastAPI documentation](http://localhost:8000/api/docs). Compose applies the database migrations before starting Uvicorn, the Celery worker, and the recurring scheduler.

## Option B — Run without Docker

Install Python, Node.js, PostgreSQL, and Redis locally. Use Node.js 22 LTS on macOS Monterey. The native setup creates a Python virtual environment under `backend/.venv`.

```bash
./scripts/setup-local-macos.sh
```

Create the local database, configure `.env`, and run migrations. Start FastAPI, the worker, Beat, and Next.js in separate terminals using the commands in the [native development guide](docs/LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md).

## Try an analysis

1. Create a project and assign Data, Sales, and Financial Analyst.
2. Save the following as `sales.csv` and upload it in Datasets.
3. Open Cleaning studio, preview removing duplicates, and save version 2.
4. Open AI analysts and enter **Total revenue by region**. The expected revenue is **150 for North and 70 for South**, with **90 total profit**.
5. Save the chart as a dashboard. Open Reports and export the analysis to a supported format.

```csv
date,region,revenue,expenses
2025-01-01,North,100,60
2025-01-02,South,70,40
2025-01-03,North,50,30
2025-01-03,North,50,30
```

## Development and deployment

- [Development setup](docs/DEVELOPMENT_SETUP.md) covers macOS, Linux, and a two-process setup using SQLite.
- [Deployment](docs/DEPLOYMENT.md) covers configuration, migrations, storage, and recovery.
- [Architecture](docs/ARCHITECTURE.md), [agent orchestration](docs/AGENT_ARCHITECTURE.md), [analyst roles](docs/ANALYST_ROLES.md), and [database design](docs/DATABASE_DESIGN.md) describe the application.
- [API documentation](docs/API_DOCUMENTATION.md) describes the resources, isolation model, and asynchronous jobs.
- [Security](docs/SECURITY.md), [testing](docs/TESTING.md), and [troubleshooting](docs/TROUBLESHOOTING.md) describe verification and operational boundaries.
- [Implementation status](docs/IMPLEMENTATION_STATUS.md) records working features, scope limits, and deployment readiness.
