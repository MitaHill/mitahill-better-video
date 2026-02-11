# SQLite Optimization

## Goals
- Avoid lock contention between API and Worker
- Keep writes fast for high-frequency progress updates
- Preserve durability without stalling GPU pipelines

## Current Settings
- WAL mode (`journal_mode=WAL`)
- `synchronous=NORMAL`
- `temp_store=MEMORY`
- `busy_timeout=30000`
- Indexes on `status` and `created_at`

## Operational Notes
- Single writer (worker) + multiple readers (API) is the preferred model.
- Avoid long transactions in API routes.
- For multi-worker scale-out, switch to PostgreSQL.
