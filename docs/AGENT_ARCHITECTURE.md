# Agent orchestration

LangGraph runs a typed state machine. The supervisor records role assignments and request mode. The planner loads the source version, records its transformation lineage, and prepares a validated SQL query when applicable. A conditional edge selects general analysis or the forecasting, model, research, comparison, or chart path. Visualization, insight generation, and validation run after execution. Report conversion runs as a separate Celery job.

Role calculations run with limited parallelism over the same immutable frame. A natural-language request may generate one read-only SQL statement. Optional OpenAI and Gemini planners receive the prompt and approved schema fields. The result contains the executed SQL, selected fields, source version and hash, assumptions, limitations, and optional provider usage.

The job trace and per-attempt status are persisted. The PostgreSQL saver can resume a recovered job from a workflow checkpoint. SQLite development uses process-local checkpoints. Explicit retries begin a fresh checkpoint generation. Each job has a recursion budget, SQL deadline, and worker timeout. Cancellation is cooperative at progress and completion boundaries.

All calculations use analytical code. Model or provider content remains untrusted, and validation rejects unsupported SQL, non-finite JSON, and missing or unauthorized input references.
