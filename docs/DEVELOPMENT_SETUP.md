# Development setup

Use Python 3.12, uv, and Node.js 24 for this SQLite workflow. On macOS Monterey, use Node.js 22 LTS. The backend package declares Python 3.11 through 3.13 support. CI uses 3.12. On macOS, install the tools with Homebrew. On Linux, use your distribution or the official installers and verify `uv --version`, `python3 --version`, and `node --version`.

## API

From the repository root, open a terminal and run

```bash
cd backend
uv sync --locked
export ANALYST_DATABASE_URL=sqlite:///./analyst.sqlite3 ANALYST_EAGER=true
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-proxy-headers
```

The local database and the volume containing Parquet files and reports are created inside `backend/`. This mode runs Celery tasks eagerly. For worker concurrency and recurring jobs, use the [native PostgreSQL and Redis setup](LOCAL_DEVELOPMENT_WITHOUT_DOCKER.md) or Docker Compose.

## Web application

In a second terminal

```bash
cd frontend
npm ci
npm run dev
```

Use `http://localhost:3000`. The origin and cookie host must match. If using another port or hostname, set `ANALYST_ORIGIN` for Uvicorn and use the same URL in your browser. `API_INTERNAL_URL` defaults to `http://127.0.0.1:8000` in Next.js.

Use `docker compose up --build --wait` from the root after creating `.env` to run the complete stack. The [README](../README.md) gives the setup commands.
