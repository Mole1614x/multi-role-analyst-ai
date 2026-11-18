# Compose operations

## Backup and restore

The recovery tool uses PostgreSQL's custom-format logical dump and archives the Compose object volume. It includes dataset versions, reports, and staged uploads. It records SHA-256 hashes for both files and checks them before restore. It excludes Redis and the Celery schedule file. Postgres persists the queued jobs and schedules. The scheduler reads those records after startup.

Use Python 3.11 or newer. Run the commands in the repository root with a configured `.env` and the backend image already built. Stop writes from API, scheduler, worker, migration tasks, and any external database or storage clients before taking a consistent backup.

```bash
docker compose stop frontend scheduler api worker
python3 scripts/compose-recovery.py backup /secure/backup/analyst-2026-11-18
docker compose up -d --wait
```

Use a new Compose project and a fresh PostgreSQL database and object volume for restore. Use separate ports when running the source and target on the same host. The recovery tool refuses a nonempty destination. Use an empty replacement target if a restore fails after writing data.

```bash
export API_PORT=18000 FRONTEND_PORT=13000
python3 scripts/compose-recovery.py restore /secure/backup/analyst-2026-11-18 --project analyst-restore
docker compose -p analyst-restore up -d --wait
```

The archive contains account records, datasets, reports, sessions, and job history. Store it in encrypted, access-controlled storage. The commands cover the default local object volume. For S3, configure a separate versioned bucket-copy and restore procedure, include objects under `datasets/`, `reports/`, and `staging/`, and reconcile objects with the same PostgreSQL backup before serving requests.

### Retention

Keep database records, dataset versions, dashboards, reports, and checkpoints across upgrades and restarts. Successful imports remove their staged upload. Failed and canceled import jobs retain their staged upload to allow retry. The scheduler removes expired authentication sessions and reset tokens. Review unused staged objects and expired backup bundles on a documented operator schedule before deleting them. Set a retention period for backup copies based on the deployment's recovery point objective and privacy policy. No time-based data or report deletion is enabled.

### Monitoring

Use the worker container's health check to verify that its named Celery worker answers through Redis. The API's `/api/health/ready` checks PostgreSQL and Redis readiness. Scrape `/metrics` on the internal API endpoint and limit it at your ingress.

- `analyst_job_records` reports persisted counts by job kind, status, and failure code, including retry exhaustion.
- `analyst_broker_queue_depth` reports queued deliveries across the default Redis priority buckets. Duplicate deliveries can exist while the scheduler is recovering jobs.
- `analyst_job_metrics_database_up` and `analyst_job_metrics_broker_up` distinguish an unavailable dependency from an empty queue.
- The worker retries recoverable database errors and recovers abandoned executions on the scheduler's next poll. Manual retries start a fresh recovery budget and keep completed workflow steps.

### Isolated verification

Use a disposable Compose project and a protected fixture file. The exercise registers two synthetic tenants, checks data and report isolation, verifies the upload and SQL gates, and runs 16 analyses with up to four concurrent requests. It prints elapsed time, p95 job completion time, and correctness. Use the same fixture after restoring to a fresh deployment to check the account, project, dashboard, job history, and byte-identical report and dataset versions.

```bash
python3 scripts/verify-deployment.py seed http://127.0.0.1:8000 /tmp/analyst-drill.json
python3 scripts/verify-deployment.py exercise http://127.0.0.1:8000 /tmp/analyst-drill.json
python3 scripts/verify-deployment.py verify http://127.0.0.1:18000 /tmp/analyst-drill.json
```

The smoke workload measures one small deployment. Capacity sizing, sustained and mixed-load benchmarks, independent security review, and ingress TLS still belong to the deployment's rollout plan.
