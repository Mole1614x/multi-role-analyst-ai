# Analyst Workspace

Analyst Workspace is a multi-role analytics application. It imports versioned datasets, runs checked DuckDB queries and specialist calculations, and saves charts, dashboards, and reports with the underlying evidence. The core workflow runs locally without a model API key.

## Quick start

Install Python 3.11 through 3.13 and Node.js 22.13 or newer. Use the latest Node.js 22 LTS release on macOS Monterey.

```bash
git clone https://github.com/Mole1614x/multi-role-analyst-ai.git
cd multi-role-analyst-ai
npm install
npm run setup
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) and create an account. FastAPI is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Press Ctrl+C to stop both servers.

`npm install` runs setup automatically. Use `npm run setup` to recheck dependencies and apply migrations. Setup creates `backend/.venv` and an isolated `.env.development.local` when needed. Your SQLite database and files stay under `backend/data/`.

The default workspace uses SQLite and a bounded background worker. Docker, PostgreSQL, Redis, and Celery are optional for local development. Configure an OpenAI or Gemini API key in `.env.development.local` to enable AI-assisted planning. [Local development guide](docs/DEVELOPMENT_SETUP.md)

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

- [Development setup](docs/DEVELOPMENT_SETUP.md) covers npm commands, local storage, and troubleshooting.
- [Deployment](docs/DEPLOYMENT.md) covers Docker Compose and production services. [Compose operations](docs/OPERATIONS.md) covers recovery, retention, and monitoring. [Native services guide](docs/LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md) covers running PostgreSQL, Redis, and Celery yourself.
- [Architecture](docs/ARCHITECTURE.md), [agent orchestration](docs/AGENT_ARCHITECTURE.md), [analyst roles](docs/ANALYST_ROLES.md), and [database design](docs/DATABASE_DESIGN.md) describe the application.
- [API documentation](docs/API_DOCUMENTATION.md) describes the resources, isolation model, and asynchronous jobs.
- [Specialist methods](docs/SPECIALIST_ANALYSIS.md) lists formulas and input fields. [Configured connectors](docs/CONNECTORS.md) covers Sheets, MySQL, REST, and PostgreSQL imports.
- [Security](docs/SECURITY.md), [testing](docs/TESTING.md), and [troubleshooting](docs/TROUBLESHOOTING.md) describe verification and operational boundaries.
- [Implementation status](docs/IMPLEMENTATION_STATUS.md) records working features, scope limits, and deployment readiness.
