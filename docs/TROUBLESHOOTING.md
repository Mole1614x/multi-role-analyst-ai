# Troubleshooting

| Symptom | Investigation |
| --- | --- |
| Browser receives 403 on a form | Match the browser URL to `ANALYST_ORIGIN`; check scheme and port |
| API readiness fails | Inspect the migration exit status, PostgreSQL logs, and Redis health |
| Jobs stay queued | Check the Redis broker, Celery worker health, and Beat dispatch logs |
| A worker exits during a job | Beat recovers expired jobs; review the trace, attempt count, and task timeout |
| Dataset import is rejected | Check the documented file type, size, table or sheet name, and data limits |
| A SQL query is rejected | Inspect the generated SELECT and registered aliases; unsupported functions and external access are blocked |
| Forecast fails with an irregular frequency | Aggregate input to a complete regular cadence before running the forecast |
| Research or password reset is unavailable | Configure the relevant Brave Search or SMTP settings |
| An artifact is missing | Verify volume sharing or S3 permissions and review the report job trace |
| Build dependencies fail TLS verification | Install the trusted build CA with BuildKit as documented in Deployment |

API responses include `X-Request-ID`. Uvicorn logs that identifier and the HTTP outcome. Worker failures log job IDs and error classes. Avoid sharing raw job or dataset content when reporting an incident.
