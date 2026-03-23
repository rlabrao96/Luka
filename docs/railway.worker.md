# Railway Worker Service Setup

The ARQ worker runs as a **second Railway service** configured manually in the Railway dashboard:

- **Service name:** luka-worker
- **Root Directory:** backend/
- **Build:** Same Dockerfile as API
- **Start command:** `python -m arq worker.WorkerSettings`
- **Environment variables:** Same as API service (share Redis URL, DB URL, etc.)

Railway's `railway.toml` does not reliably support multi-service `[[services]]` blocks — use the dashboard for the worker.
