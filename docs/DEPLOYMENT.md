# Deployment

The Compose files provide a reproducible single-host deployment. API and web ports bind to loopback. PostgreSQL and Redis remain inside the service network. Deployment startup runs `alembic upgrade head` once before the Uvicorn API starts.

Set `ANALYST_ORIGIN` to the public HTTPS hostname and `ANALYST_COOKIE_SECURE=true` behind a TLS ingress. Forward requests to the web service and allow streaming without response buffering. Configure upload body and worker resource limits appropriate to the workload. Keep the API health and metrics ports private. Scrape `/metrics` on the API, and use Celery worker logs for worker execution visibility.

Copy `.env.example` to `.env`, restrict permissions, and populate the required database password using a URL-safe secret. Set these optional controls when needed.

| Setting | Purpose |
| --- | --- |
| `ANALYST_LLM_PROVIDER`, `ANALYST_LLM_MODEL`, `ANALYST_LLM_API_KEY` | OpenAI or Gemini planning |
| `ANALYST_LLM_INPUT_COST_PER_MILLION`, `ANALYST_LLM_OUTPUT_COST_PER_MILLION` | Optional estimated cost from provider token counts |
| `ANALYST_RESEARCH_API_KEY` | Brave Search evidence discovery |
| `ANALYST_SMTP_HOST`, `ANALYST_SMTP_FROM`, `ANALYST_SMTP_USERNAME`, `ANALYST_SMTP_PASSWORD` | Password reset delivery through STARTTLS |
| `ANALYST_S3_BUCKET`, `ANALYST_S3_ENDPOINT` | Private S3-compatible object bucket and optional custom endpoint |
| `ANALYST_ADMIN_USER_IDS`, `ANALYST_POSTGRES_SOURCES` | Operator account UUIDs and named read-only PostgreSQL DSNs |

Use one Beat scheduler per deployment. Back up PostgreSQL and the object volume or bucket together. Retain Redis persistence for queued tasks. Test restoring these backups before onboarding sensitive data. For container builds behind a trusted proxy, provide the full CA bundle as a BuildKit build secret named `build_ca` to the backend and frontend build definitions.

```bash
docker compose up --build --wait
docker compose ps
docker compose logs --tail=100 api worker scheduler
```
