# Development setup

Install Python 3.11, 3.12, or 3.13 and Node.js 22.13 or later. On macOS Monterey, use the latest supported Node.js 22 LTS patch. Current Node.js 24 binaries require a newer macOS release. On Windows, the launcher uses the Python interpreter in `backend/.venv/Scripts`. WSL can also run the Linux workflow.

```bash
npm install
npm run setup
npm run dev
```

Open `http://localhost:3000`. FastAPI is available at `http://127.0.0.1:8000`, and `/docs` opens the API documentation. Wait for the launcher to report readiness. Ctrl+C stops Next.js and Uvicorn.

## What setup does

- Finds a supported Python and creates `backend/.venv` if absent. Set `PYTHON_BIN` if you have multiple interpreters.
- Installs the backend requirements and the editable app package. Next.js dependencies come from `frontend/package-lock.json`.
- Creates `.env.development.local` from `.env.development.example` when needed, checks imports, and runs Alembic migrations.
- Reuses existing dependency installations when the manifest fingerprints match.

## Data and jobs

The development database is `backend/data/analyst_dev.db`. Uploaded datasets and generated report files live in `backend/data/storage`. Back up both together to retain accounts, project history, conversations, dashboards, and reports.

If you already have a SQLite workspace from the earlier setup, point the development file at its original database and storage paths. Common legacy values are `DATABASE_URL=sqlite:///./analyst.sqlite3` and `ANALYST_STORAGE_DIR=./storage`, both relative to `backend/`. Setup applies migrations to the selected SQLite database.

The local worker runs imports, profiling, analyses, and report generation on one background thread. At most 16 jobs can be running or queued across the server. Job state and completed results persist in SQLite. Queued and in-flight work is not durable across restarts. On startup, unfinished local jobs are marked failed and can be retried from Execution & schedules. Recurring schedules require the Redis and Celery deployment.

`.env.development.local` is the configuration for the root npm launcher. Deployment continues to use `.env` and can use [Docker Compose](DEPLOYMENT.md) or [native PostgreSQL, Redis and Celery](LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md).

## Analyst providers

The existing analyst roles and deterministic tools run with the default setup. To enable AI-assisted planning, set `ANALYST_LLM_PROVIDER=openai` or `gemini` and `ANALYST_LLM_API_KEY` in `.env.development.local`, then restart the app. The AI analysts page shows whether a provider is configured. Brave Search is configured separately with `ANALYST_RESEARCH_API_KEY`.

## Project commands

| Command | Purpose |
| --- | --- |
| `npm run setup` | Install dependencies and apply pending SQLite migrations |
| `npm run dev` | Start both dev servers and show their URLs |
| `npm test` | Run pytest and Playwright against an isolated temporary SQLite workspace |
| `npm run lint` | Check Python style and frontend lint and types |
| `npm run build` | Build the production Next.js bundle |

The browser tests install Chromium if needed. Linux may require Playwright's system browser libraries. Use `npm exec --prefix frontend -- playwright install --with-deps chromium` when needed, or set `CHROMIUM_PATH` to an installed test browser.

## Troubleshooting

| Symptom | Resolution |
| --- | --- |
| Python missing or incompatible | Install Python 3.11 through 3.13. Set `PYTHON_BIN` to its executable before setup. Move an incompatible `backend/.venv` aside first. |
| Dependency or editable installation fails | Check the package error printed by pip and run `npm run setup`. Intel Monterey may need Command Line Tools and CMake for the Argon2 bindings. See the [Monterey notes](LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md#macos-monterey-12). |
| Port 8000 or 3000 is occupied | Close the other process or edit `BACKEND_URL` or `FRONTEND_URL` in `.env.development.local`, then rerun `npm run dev`. |
| Browser form receives 403 | Use the exact frontend URL printed by the launcher. Browser calls use the same-origin Next.js API proxy. |
| An old environment tries to use PostgreSQL | Check for an exported `DATABASE_URL` or `ANALYST_DATABASE_URL` and unset it for this terminal. The root launcher expects a SQLite development database. |
| Local analysis queue is full | Wait for active jobs to finish, then retry the failed job from Execution & schedules. |
