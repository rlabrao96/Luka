# Luka — Local Development

## Prerequisites

- Python 3.12+
- Node.js 20+
- Redis (local or Docker: `docker run -d -p 6379:6379 redis`)
- Supabase project (for auth and database)

## Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your Supabase URL, keys, Redis URL, etc.

# Run migrations
alembic upgrade head

# Start API server
uvicorn main:app --reload --port 8000

# Start ARQ worker (separate terminal)
cd backend && python -m arq worker.WorkerSettings
```

## Frontend Setup

```bash
cd frontend
npm install

# Configure environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL

# Start dev server
npm run dev   # http://localhost:3000
```

## Running Tests

```bash
# Backend (requires .env with valid DATABASE_URL for integration tests)
cd backend
pytest tests/ -x -q

# Frontend
cd frontend
npm run build   # Type-check + build
```

## Project Conventions

- **Backend modules:** Each feature area lives in `modules/<name>/` with `models.py`, `router.py`, `schemas.py`, `service.py`
- **Frontend hooks:** Custom hooks in `app/lib/hooks/` wrap TanStack Query for data fetching
- **State management:** Zustand for client state (userId, householdId), React Query for server state
- **Styling:** Tailwind CSS with custom `luka-*` design tokens defined in `globals.css`
- **Auth pattern:** `Depends(get_current_user)` on every protected route — validates JWT locally
