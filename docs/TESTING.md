# Testing

Run the backend suite after syncing the lockfile.

```bash
cd backend
uv sync --locked
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
uv run pytest -q
```

Pytest uses a migrated, temporary SQLite database and isolated object storage. It checks access isolation, deterministic calculations, imports, SQL restrictions, agent routing, retries, and six export formats. Known-answer fixture values are independently asserted.

Start the stack before running the browser tests.

```bash
cd frontend
npm ci
npm run check
npm run build
npx playwright install chromium
npm test
```

The browser suite covers registration, login, project creation and re-opening, upload, profiling, cleaning, SQL drafting and execution, multi-role analysis, chart filtering, dashboard persistence, export download, and mobile navigation. Set `PLAYWRIGHT_BASE_URL` for an alternate deployment URL. Set `CHROMIUM_PATH` when testing against a compatible system Chromium.
