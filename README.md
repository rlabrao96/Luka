# Luka

Chilean personal finance SaaS for individuals and couples. Captures bank transactions via email push notifications and Fintoc open banking, categorizes via LLM, actions via WhatsApp, visualizes on a responsive web dashboard.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI (Python 3.12) + ARQ (async jobs) + Redis |
| **Database** | Supabase PostgreSQL + SQLAlchemy async + Alembic |
| **Frontend** | Next.js 14 (App Router) + Tailwind CSS 4 + shadcn/ui + Recharts |
| **Auth** | Supabase Auth — Google OAuth + Microsoft OAuth |
| **Hosting** | Railway (backend + worker) + Vercel (frontend) |

## Quick Start

```bash
# Backend
cd backend
cp .env.example .env          # Fill in Supabase, Redis, Fintoc, OpenAI keys
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn main:app --reload     # http://localhost:8000

# Frontend
cd frontend
cp .env.local.example .env.local   # Set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_API_URL
npm install
npm run dev                         # http://localhost:3000
```

## Project Structure

```
backend/
  core/           Config, database, security, cache
  modules/        auth, households, transactions, merchants, email, whatsapp, fintoc, budgets, bank_accounts
  jobs/           ARQ worker tasks and cron jobs
  alembic/        Database migrations (12 versions)
  tests/          22 test files, 31+ tests

frontend/
  app/
    (auth)/       Login, onboarding (setup-household, connect-bank, verify-whatsapp)
    (dashboard)/  Home, transactions, budgets, household, settings
    (public)/     Privacy, terms, data-deletion
    lib/          API client, Zustand store, React Query hooks, Supabase clients

docs/
  architecture.md    System architecture and design decisions
  api-reference.md   All 28 API endpoints
  deployment.md      Railway + Vercel deployment guide
  development.md     Local development setup
  roadmap.md         Feature roadmap
```

## Documentation

- [Architecture](docs/architecture.md) — System diagram, auth flow, data model
- [API Reference](docs/api-reference.md) — All endpoints with schemas
- [Deployment](docs/deployment.md) — Production setup guide
- [Development](docs/development.md) — Local dev environment
- [Roadmap](docs/roadmap.md) — Feature priorities and timeline
- [Design Specs](docs/superpowers/specs/) — Original design documents
