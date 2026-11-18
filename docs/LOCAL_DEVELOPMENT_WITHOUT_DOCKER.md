# Local development without Docker

The native stack runs FastAPI, the Celery worker, and Celery Beat from `backend/.venv`. Next.js uses Node.js and installs packages into `frontend/node_modules`. PostgreSQL and Redis run as local services.

Run commands from the repository root unless a command changes directories.

## 1. Install the prerequisites

### macOS Monterey 12

Use your existing Python 3.11 and install the latest Node.js 22 LTS patch. Node.js 22 supports macOS 11 and later. Choose the macOS installer for your processor from the [Node.js 22 release directory](https://nodejs.org/download/release/latest-v22.x/). Check both runtimes in a new terminal.

```bash
python3.11 --version
node --version
npm --version
```

If your Homebrew installation can build both services for Monterey, install and start them with these commands.

```bash
brew install postgresql@17 redis
brew services start postgresql@17
brew services start redis
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
```

Current Homebrew bottles may require a newer macOS release. If PostgreSQL installation fails, install [Postgres.app with PostgreSQL 17](https://postgresapp.com/downloads.html), open it, initialize a server, and add its tools to the current shell.

```bash
export PATH="/Applications/Postgres.app/Contents/Versions/17/bin:$PATH"
```

If Homebrew cannot install Redis, build a supported Redis release with Apple's Command Line Tools. Download and extract the official tarball as described in the [Redis source installation guide](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-from-source/). From the extracted directory run the following in a separate terminal and leave it open.

```bash
make MALLOC=libc
./src/redis-server --bind 127.0.0.1 --port 6379
```

Use `./src/redis-cli ping` to check this source-built server.

### Newer macOS

Use Python 3.11 through 3.13. Install PostgreSQL and Redis with Homebrew. Choose a Node.js LTS installer compatible with your macOS version, such as [Node.js 24 LTS](https://nodejs.org/download/release/latest-v24.x/) on macOS 13.5 or later.

```bash
brew install python@3.11 postgresql@17 redis
brew services start postgresql@17
brew services start redis
export PATH="$(brew --prefix postgresql@17)/bin:$PATH"
```

### Linux

On Debian or Ubuntu, install the system services and a Python interpreter that supports `venv`. The distribution's default Python must be 3.11 through 3.13. Install a current Node.js 22 or 24 LTS build through a package manager or the [official Node.js downloads](https://nodejs.org/en/download).

```bash
sudo apt install python3 python3-venv postgresql redis-server
sudo systemctl start postgresql redis-server
sudo -u postgres psql -d postgres
```

Use the last command in place of `psql -d postgres` in step 2. Other distributions may use different service names.

### Windows

Use Ubuntu under WSL 2 for the native stack. Install Python, Node.js, PostgreSQL and Redis inside the same WSL distribution, then follow the Linux instructions from its Bash shell. If systemd is unavailable, start the services with `sudo service postgresql start` and `sudo service redis-server start`. Open `http://localhost:3000` in the Windows browser.

## 2. Create the PostgreSQL role and database

Connect as a PostgreSQL administrator. On macOS with Homebrew or Postgres.app this is usually the account that initialized the server.

```bash
psql -d postgres
```

In `psql`, inspect existing roles and databases with `\du` and `\l`. For a new development database, run the commands below. The password prompt keeps your password out of the command line. If the role or database already exists, configure the application to use it or pick a new name.

```sql
CREATE ROLE analyst LOGIN;
\password analyst
CREATE DATABASE analyst OWNER analyst;
\q
```

Check the application login over TCP and confirm Redis replies with `PONG`.

```bash
psql -h 127.0.0.1 -p 5432 -U analyst -d analyst -W -c 'SELECT 1;'
redis-cli ping
```

## 3. Install project dependencies and configure the environment

```bash
PYTHON_BIN=python3.11 ./scripts/setup-local-macos.sh --dev
```

Use your chosen Python executable if it has a different name. The script also works on Linux and WSL. It creates `backend/.venv` when needed, installs requirements and the editable Python package, and runs `npm ci` for Next.js. It copies `.env.example` to `.env` when the latter is absent. Omit `--dev` to install the runtime Python requirements alone.

To install these pieces manually from the repository root:

```bash
if [ ! -d backend/.venv ]; then python3.11 -m venv backend/.venv; fi
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m pip install -e ./backend
(cd frontend && npm ci)
if [ ! -e .env ]; then (umask 077; cp .env.example .env); fi
```

Set these values in `.env`. Replace the password placeholder with the PostgreSQL role password you just chose. Quote values that contain spaces or dotenv syntax. Keep this file local.

```dotenv
APP_ENV=development
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=analyst
POSTGRES_USER=analyst
POSTGRES_PASSWORD=<your local role password>
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://127.0.0.1:8000
```

- Leave `DATABASE_URL` blank to build a connection using the `POSTGRES_*` values. SQLAlchemy safely encodes the password. An explicit `DATABASE_URL` can use `postgresql+psycopg://` or `postgresql://`. Percent-encode reserved characters in credentials embedded in a URL.
- Celery uses `REDIS_URL` as its default broker. When configured, `CELERY_BROKER_URL` selects a different Redis database or instance. `CELERY_RESULT_BACKEND` is optional. Analysis results remain available from the application database.
- Celery processes jobs in the background when a broker is configured. If your existing `.env` explicitly sets `ANALYST_EAGER=true`, change it to `false` for this setup.
- Existing aliases such as `ANALYST_DATABASE_URL`, `ANALYST_REDIS_URL`, and `ANALYST_ORIGIN` are supported. Within the same environment source, the prefixed value wins. Backend settings load the repository `.env`, then `backend/.env` if present. Shell variables override file values.
- The frontend uses same-origin `/api` requests through a Next.js rewrite. The launcher reads `BACKEND_URL` from the backend settings. The existing `API_INTERNAL_URL` still overrides that destination. For a manual `npm run dev`, use the default address or set a custom `BACKEND_URL` in the shell or `frontend/.env.local`. Open the browser at the exact `FRONTEND_URL`. Authentication checks the origin of browser writes.

## 4. Check services and apply migrations

```bash
./scripts/check-local-services.sh
(cd backend && .venv/bin/python -m alembic upgrade head)
(cd backend && .venv/bin/python -m alembic current)
```

Use a development database you intend to migrate. Alembic updates the schema. The setup script installs dependencies and leaves schema changes to this step.

## 5. Start the application

From the repository root, run each command in its own terminal.

| Terminal | Command |
| --- | --- |
| FastAPI | `./scripts/start-backend.sh` |
| Celery worker | `./scripts/start-worker.sh` |
| Celery Beat | `./scripts/start-worker.sh beat` |
| Next.js | `./scripts/start-frontend.sh` |

Beat is needed for recurring analyses. Keep one Beat process for this workspace. The worker runs `python -m celery -A app.services.jobs:celery worker --loglevel=info --concurrency=2` from the backend virtual environment.

To start FastAPI and Next.js manually with the default ports, use these commands in separate terminals.

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

Open [the application](http://localhost:3000) and [the API documentation](http://127.0.0.1:8000/docs). The readiness URL is [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health). Run the following from the repository root to check the API, Next.js proxy, and registered Celery tasks.

```bash
./scripts/check-local-services.sh --running
```

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Setuptools reports multiple top-level packages | Update the checkout to the version with explicit `app` package discovery. Re-run `python -m pip install -e ./backend` inside the virtual environment. |
| `requirements.txt` is missing | Run the setup script at the project root or pass `-r backend/requirements.txt` to pip. Confirm the checkout has the native setup changes. |
| PostgreSQL connection refused | Check `pg_isready -h 127.0.0.1 -p 5432`, then confirm the service and `POSTGRES_HOST` and `POSTGRES_PORT`. |
| PostgreSQL authentication fails | Run the TCP `psql` check above. Review the role, database, password and any explicit URL or environment override. |
| Redis connection refused | Start Redis and run `redis-cli ping`. Match the configured broker URL to the Redis service. |
| Port 8000 is already in use | Inspect `lsof -nP -iTCP:8000 -sTCP:LISTEN` and set `BACKEND_URL=http://127.0.0.1:8001`. Restart both launchers to update the rewrite. |
| Port 3000 is already in use | Set `FRONTEND_URL=http://localhost:3001`. Update `ANALYST_ORIGIN` too if present, restart both launchers, and use the new browser URL. |
| Environment variables are missing | The native scripts use the repository `.env` and the optional backend overrides. Use `./scripts/check-local-services.sh` to check the resolved setup. |
| Alembic migration fails | Run from `backend/` with its virtual environment. Confirm the role owns the development database, check `alembic current`, and inspect the reported migration error. |
| Python is incompatible | Use Python 3.11, 3.12, or 3.13. Move an existing incompatible `backend/.venv` aside and run setup with `PYTHON_BIN=python3.11`. |
| JavaScript modules are missing | Run `npm ci` in `frontend/`. On Monterey, verify that `node --version` points to a current Node.js 22 build. |
| The proxy returns 403 on a form | Match the browser URL to `FRONTEND_URL`, including the scheme, hostname, and port. Check for an `ANALYST_ORIGIN` override. |
