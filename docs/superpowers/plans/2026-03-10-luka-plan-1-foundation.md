# Luka — Plan 1: Foundation

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the Luka monorepo with a working FastAPI backend, all database migrations, Supabase Auth (Google + Microsoft OAuth), household creation, partner invite flow, and Next.js frontend scaffold — fully deployable to Railway + Vercel.

**Architecture:** FastAPI backend with SQLAlchemy async + Alembic migrations against Supabase PostgreSQL. Next.js frontend with Supabase Auth for OAuth. Monorepo with `backend/` and `frontend/` directories. Pre-commit hooks enforced from day one.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, asyncpg, Alembic, pytest, pytest-asyncio, uv (package manager), Next.js 14, Tailwind CSS, shadcn/ui, Supabase Auth, Railway, Vercel

**Spec:** `docs/superpowers/specs/2026-03-10-finanzas-personales-design.md`

---

## Chunk 1: Repo, Project Scaffold & Pre-commit

### File Map

```
luka/                              ← monorepo root (rename working dir)
├── .gitignore
├── .pre-commit-config.yaml
├── README.md
├── backend/
│   ├── pyproject.toml             ← deps: fastapi, sqlalchemy, asyncpg, alembic, redis, pytest...
│   ├── .env.example
│   ├── main.py                    ← FastAPI app factory
│   ├── worker.py                  ← ARQ worker entry point
│   └── core/
│       ├── __init__.py
│       ├── config.py              ← Settings (pydantic-settings, reads .env)
│       └── database.py            ← async engine + session factory
└── frontend/
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config.ts
    ├── components.json            ← shadcn/ui config
    └── app/
        ├── layout.tsx
        └── globals.css
```

---

### Task 1: Initialize Git Repo and Pre-commit

**Files:**
- Create: `.gitignore`
- Create: `.pre-commit-config.yaml`
- Create: `README.md`

- [ ] **Step 1: Initialize git and create .gitignore**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/Finanzas Personales"
git init
```

Create `.gitignore`:
```
# Python
__pycache__/
*.pyc
*.pyo
.venv/
.env
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/
htmlcov/
.coverage

# Node
node_modules/
.next/
.vercel/
*.local

# OS
.DS_Store

# Secrets baseline (detect-secrets)
.secrets.baseline
```

- [ ] **Step 2: Create pre-commit config**

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

- [ ] **Step 3: Install pre-commit and initialize secrets baseline**

```bash
pip install pre-commit detect-secrets
detect-secrets scan > .secrets.baseline
pre-commit install
```

Expected: `pre-commit installed at .git/hooks/pre-commit`

- [ ] **Step 4: Create README.md**

```markdown
# Luka

Chilean personal finance app for individuals and couples.

## Structure
- `backend/` — FastAPI + ARQ + SQLAlchemy
- `frontend/` — Next.js 14 + Tailwind + shadcn/ui

## Docs
- Spec: `docs/superpowers/specs/2026-03-10-finanzas-personales-design.md`
- Plans: `docs/superpowers/plans/`
```

- [ ] **Step 5: Initial commit**

```bash
git add .gitignore .pre-commit-config.yaml .secrets.baseline README.md docs/
git commit -m "chore: initialize Luka monorepo with pre-commit and docs"
```

---

### Task 2: Bootstrap FastAPI Backend

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/main.py`
- Create: `backend/worker.py`
- Create: `backend/core/__init__.py`
- Create: `backend/core/config.py`
- Create: `backend/core/database.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Create pyproject.toml**

```bash
mkdir -p backend/tests backend/core backend/modules
```

Create `backend/pyproject.toml`:
```toml
[project]
name = "luka-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.29.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic-settings>=2.2.0",
    "redis[hiredis]>=5.0.0",
    "arq>=0.25.0",
    "httpx>=0.27.0",
    "python-jose[cryptography]>=3.3.0",
    "supabase>=2.4.0",
    "openai>=1.30.0",
    "rapidfuzz>=3.9.0",
    "tenacity>=8.3.0",
    "google-auth>=2.29.0",
    "slowapi>=0.1.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.3.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Install dependencies with uv**

```bash
cd backend
pip install uv
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Expected: All packages installed without errors.

- [ ] **Step 3: Create .env.example**

Create `backend/.env.example`:
```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/luka

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# Redis
REDIS_URL=redis://localhost:6379

# Gmail (Google Cloud Pub/Sub)
PUBSUB_AUDIENCE=https://your-railway-app.railway.app/webhooks/gmail

# Outlook
OUTLOOK_CLIENT_STATE=change-me-random-secret
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=

# WhatsApp
WHATSAPP_APP_SECRET=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=

# Fintoc
FINTOC_API_KEY=

# LLM
OPENAI_API_KEY=

# App
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

- [ ] **Step 4: Write failing test for health endpoint**

Create `backend/tests/test_health.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_returns_ok(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "luka"}
```

Create `backend/tests/conftest.py`:
```python
import pytest
from fastapi import FastAPI


@pytest.fixture
def app() -> FastAPI:
    from main import create_app
    return create_app()
```

- [ ] **Step 5: Run test to verify it fails**

```bash
cd backend
pytest tests/test_health.py -v
```

Expected: `FAILED — ImportError: cannot import name 'create_app' from 'main'`

- [ ] **Step 6: Create core/config.py**

Create `backend/core/config.py`:
```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/luka"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    redis_url: str = "redis://localhost:6379"
    pubsub_audience: str = ""
    outlook_client_state: str = "dev-secret"
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    fintoc_api_key: str = ""
    openai_api_key: str = ""
    frontend_url: str = "http://localhost:3000"
    environment: str = "development"


settings = Settings()
```

- [ ] **Step 7: Create core/database.py**

Create `backend/core/database.py`:
```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 8: Create main.py**

Create `backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title="Luka API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "app": "luka"}

    return app


app = create_app()
```

- [ ] **Step 9: Run test to verify it passes**

```bash
pytest tests/test_health.py -v
```

Expected: `PASSED`

- [ ] **Step 10: Create worker.py**

Create `backend/worker.py`:
```python
import redis.asyncio as aioredis
from arq.connections import RedisSettings
from core.config import settings


async def startup(ctx: dict) -> None:
    ctx["redis"] = await aioredis.from_url(settings.redis_url)


async def shutdown(ctx: dict) -> None:
    await ctx["redis"].aclose()


class WorkerSettings:
    functions = []  # jobs registered in later plans
    cron_jobs = []
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)  # must be RedisSettings, not str
```

- [ ] **Step 11: Commit**

```bash
git add backend/
git commit -m "feat: bootstrap FastAPI backend with health endpoint and config"
```

---

### Task 3: Bootstrap Next.js Frontend

**Files:**
- Create: `frontend/` (via create-next-app)
- Modify: `frontend/tailwind.config.ts` — add Luka blue palette
- Create: `frontend/app/globals.css`

- [ ] **Step 1: Scaffold Next.js project**

```bash
cd "/Users/rlabrao/Documents/Proyectos AI/Finanzas Personales"
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir=false \
  --import-alias="@/*"
```

Answer prompts: yes to all defaults.

- [ ] **Step 2: Install shadcn/ui**

```bash
cd frontend
npx shadcn@latest init
```

When prompted:
- Style: Default
- Base color: Slate
- CSS variables: yes

- [ ] **Step 3: Install core shadcn components**

```bash
npx shadcn@latest add card button badge table tabs avatar separator
```

- [ ] **Step 4: Install additional dependencies**

```bash
npm install @supabase/supabase-js @supabase/ssr \
  @tanstack/react-query zustand recharts \
  lucide-react clsx tailwind-merge
```

- [ ] **Step 5: Add Luka design tokens to tailwind.config.ts**

Edit `frontend/tailwind.config.ts` — extend the `theme.extend.colors` section:
```typescript
colors: {
  luka: {
    primary:   "#2563EB",
    light:     "#EFF6FF",
    sky:       "#38BDF8",
    dark:      "#0F172A",
    muted:     "#64748B",
    success:   "#10B981",
    danger:    "#EF4444",
  },
},
```

- [ ] **Step 6: Create globals.css with base styles**

Replace `frontend/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  --background: #EFF6FF;
  --foreground: #0F172A;
}

body {
  background-color: var(--background);
  color: var(--foreground);
  font-family: var(--font-geist-sans), system-ui, sans-serif;
}
```

- [ ] **Step 7: Create frontend/.env.local.example**

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 8: Verify frontend starts**

```bash
npm run dev
```

Expected: Server starts at `http://localhost:3000` without errors.

- [ ] **Step 9: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat: scaffold Next.js frontend with Luka design system"
```

---

## Chunk 2: Database Schema & Migrations

### File Map

```
backend/
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py     ← all 12 tables in one autogenerated migration
└── tests/
    └── test_migrations.py
```

> **Note:** `alembic revision --autogenerate` produces a single file with a hash prefix (e.g. `a3f2b1_initial_schema.py`). The spec's multi-file breakdown is logical documentation only. In production, additional migrations will be added as separate files with `--rev-id` flags.

---

### Task 4: Alembic Setup and Core Tables

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_core_tables.py`
- Create: `backend/tests/test_migrations.py`

- [ ] **Step 1: Initialize Alembic**

```bash
cd backend
alembic init alembic
```

- [ ] **Step 2: Configure alembic/env.py**

Replace `backend/alembic/env.py`:
```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from core.config import settings
from core.database import Base

# import all models so Base.metadata knows about them
import modules.auth.models  # noqa: F401
import modules.households.models  # noqa: F401
import modules.merchants.models  # noqa: F401
import modules.transactions.models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Create auth models**

Create `backend/modules/__init__.py` and `backend/modules/auth/__init__.py`:
```bash
mkdir -p backend/modules/auth backend/modules/households \
         backend/modules/merchants backend/modules/transactions
touch backend/modules/__init__.py \
      backend/modules/auth/__init__.py \
      backend/modules/households/__init__.py \
      backend/modules/merchants/__init__.py \
      backend/modules/transactions/__init__.py
```

Create `backend/modules/auth/models.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    # phone_whatsapp stored in Supabase Vault — not a DB column
    whatsapp_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_provider: Mapped[str] = mapped_column(String, default="gmail")
    mail_watch_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    mail_watch_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 4: Create household models**

Create `backend/modules/households/models.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'individual' | 'couple'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, default="member")  # 'owner' | 'member'
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdInvite(Base):
    __tablename__ = "household_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    invited_email: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    bank_name: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)  # 'personal' | 'joint'
    cardholder_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email_sender_pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HouseholdBudget(Base):
    __tablename__ = "household_budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_accounts.id"), nullable=False)
    month: Mapped[datetime.date] = mapped_column(Date, nullable=False)  # DATE not TIMESTAMP
    budgeted: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    source: Mapped[str] = mapped_column(String, default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 5: Create merchant models**

Create `backend/modules/merchants/models.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_suggested_categories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    total_selections: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantCategorySelection(Base):
    __tablename__ = "merchant_category_selections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 6: Create transaction models**

Create `backend/modules/transactions/models.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id"), nullable=False)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bank_accounts.id"), nullable=True)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("merchants.id"), nullable=True)
    raw_merchant_name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="CLP")
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)  # denormalized
    source: Mapped[str] = mapped_column(String, nullable=False)  # gmail|outlook|fintoc|manual
    status: Mapped[str] = mapped_column(String, default="pending")
    fintoc_id: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_email_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransactionSplit(Base):
    __tablename__ = "transaction_splits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    split_type: Mapped[str] = mapped_column(String, nullable=False)  # personal|partner|shared
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProcessedWebhook(Base):
    __tablename__ = "processed_webhooks"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FailedJob(Base):
    __tablename__ = "failed_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 7: Generate and run migration**

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Expected: All tables created in Supabase. Check Supabase dashboard — you should see all tables listed.

- [ ] **Step 8: Write migration test**

Create `backend/tests/test_migrations.py`:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_all_tables_exist(db: AsyncSession):
    expected_tables = [
        "users", "households", "household_members", "household_invites",
        "bank_accounts", "household_budgets",
        "merchants", "merchant_category_selections",
        "transactions", "transaction_splits",
        "processed_webhooks", "failed_jobs",
    ]
    for table in expected_tables:
        result = await db.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
            {"t": table}
        )
        assert result.scalar() == 1, f"Table '{table}' not found"
```

Update `backend/tests/conftest.py` to add db fixture with SAVEPOINT rollback for test isolation:
```python
import pytest
import uuid
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from core.config import settings


@pytest.fixture
def app() -> FastAPI:
    from main import create_app
    return create_app()


@pytest.fixture
async def db():
    """
    Wraps each test in a SAVEPOINT and rolls back after.
    Tests never write permanent rows — suite is fully repeatable.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()
    await engine.dispose()


@pytest.fixture
def mock_user():
    from modules.auth.models import User
    return User(
        id=uuid.uuid4(),
        email="rafa@test.cl",
        full_name="Rafa Test",
        email_provider="gmail",
        whatsapp_verified=False,
    )


@pytest.fixture
def mock_partner():
    from modules.auth.models import User
    return User(
        id=uuid.uuid4(),
        email="cami@test.cl",
        full_name="Cami Test",
        email_provider="gmail",
        whatsapp_verified=False,
    )
```

- [ ] **Step 9: Run migration test**

```bash
pytest tests/test_migrations.py -v
```

Expected: `PASSED` — all 12 tables confirmed in the database.

- [ ] **Step 10: Commit**

```bash
git add backend/
git commit -m "feat: add all SQLAlchemy models and initial Alembic migration"
```

---

## Chunk 3: Auth & Onboarding

### File Map

```
backend/
├── core/
│   └── security.py              ← get_current_user dependency
└── modules/
    └── auth/
        ├── models.py            ← (already created)
        ├── router.py            ← GET /auth/me, POST /auth/whatsapp/verify
        ├── service.py           ← upsert_user_from_supabase, send_wa_pin
        └── schemas.py           ← UserResponse, WhatsAppVerifyRequest

frontend/
└── app/
    ├── (auth)/
    │   ├── login/
    │   │   └── page.tsx         ← Google/Microsoft OAuth buttons
    │   └── onboarding/
    │       ├── layout.tsx       ← progress stepper
    │       ├── connect-email/page.tsx
    │       ├── verify-whatsapp/page.tsx
    │       ├── setup-household/page.tsx
    │       └── connect-bank/page.tsx
    └── lib/
        ├── supabase/
        │   ├── client.ts        ← browser Supabase client
        │   └── server.ts        ← server Supabase client (SSR)
        └── api.ts               ← typed fetch wrapper for FastAPI
```

---

### Task 5: Backend Auth Middleware

**Files:**
- Create: `backend/core/security.py`
- Create: `backend/modules/auth/schemas.py`
- Create: `backend/modules/auth/service.py`
- Create: `backend/modules/auth/router.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Write failing auth test**

Create `backend/tests/test_auth.py`:
```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_me_requires_auth(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_returns_user_when_authenticated(app, mock_user):
    with patch("modules.auth.router.get_current_user", return_value=mock_user):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/auth/me", headers={"Authorization": "Bearer valid-token"})
    assert response.status_code == 200
    assert response.json()["email"] == mock_user.email
```

Both `mock_user` and `mock_partner` fixtures are already defined in `conftest.py` (Task 4, Step 8). No changes needed here.

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_auth.py -v
```

Expected: `FAILED — 404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Create core/security.py**

Create `backend/core/security.py`:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client
from core.config import settings
from modules.auth.models import User
from core.database import AsyncSessionLocal
from sqlalchemy import select

bearer_scheme = HTTPBearer()
supabase = create_client(settings.supabase_url, settings.supabase_anon_key)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    token = credentials.credentials
    try:
        user_response = supabase.auth.get_user(token)
        supabase_user = user_response.user
        if not supabase_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == supabase_user.email)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found. Complete onboarding.")
    return user
```

- [ ] **Step 4: Create auth schemas and router**

Create `backend/modules/auth/schemas.py`:
```python
import uuid
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_provider: str
    whatsapp_verified: bool

    model_config = {"from_attributes": True}


class WhatsAppVerifyRequest(BaseModel):
    phone: str   # e.g. "+56912345678"
    pin: str     # 6-digit pin
```

Create `backend/modules/auth/router.py`:
```python
from fastapi import APIRouter, Depends
from core.security import get_current_user
from modules.auth.models import User
from modules.auth.schemas import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 5: Register router in main.py**

Edit `backend/main.py` — import and include the auth router:
```python
from modules.auth.router import router as auth_router
# inside create_app(), after middleware:
app.include_router(auth_router)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_auth.py -v
```

Expected: Both tests `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add auth middleware and /auth/me endpoint"
```

---

### Task 6: Household Service (Create, Invite, Join)

**Files:**
- Create: `backend/modules/households/schemas.py`
- Create: `backend/modules/households/service.py`
- Create: `backend/modules/households/router.py`
- Create: `backend/tests/test_households.py`

- [ ] **Step 1: Write failing household tests**

Create `backend/tests/test_households.py`:
```python
import pytest
from modules.households.service import create_household, create_invite, accept_invite
from modules.households.models import Household, HouseholdInvite
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_create_individual_household(db, mock_user):
    household = await create_household(
        db=db, owner=mock_user, name="Rafa", household_type="individual"
    )
    assert household.type == "individual"
    assert household.name == "Rafa"


@pytest.mark.asyncio
async def test_create_invite_generates_token(db, mock_user):
    household = await create_household(db=db, owner=mock_user, name="Rafa & Cami", household_type="couple")
    invite = await create_invite(db=db, household=household, invited_by=mock_user, invited_email="cami@test.cl")
    assert invite.token is not None
    assert len(invite.token) > 10
    assert invite.invited_email == "cami@test.cl"


@pytest.mark.asyncio
async def test_accept_invite_adds_member(db, mock_user, mock_partner):
    household = await create_household(db=db, owner=mock_user, name="Rafa & Cami", household_type="couple")
    invite = await create_invite(db=db, household=household, invited_by=mock_user, invited_email=mock_partner.email)
    result = await accept_invite(db=db, token=invite.token, user=mock_partner)
    assert result.accepted_at is not None
```

`mock_partner` fixture is already defined in `conftest.py` (Task 4, Step 8). No changes needed here.

- [ ] **Step 2: Run to verify failures**

```bash
pytest tests/test_households.py -v
```

Expected: `FAILED — ImportError`

- [ ] **Step 3: Implement household service**

Create `backend/modules/households/service.py`:
```python
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from modules.households.models import Household, HouseholdMember, HouseholdInvite
from modules.auth.models import User


async def create_household(db: AsyncSession, owner: User, name: str, household_type: str) -> Household:
    household = Household(name=name, type=household_type)
    db.add(household)
    await db.flush()

    member = HouseholdMember(household_id=household.id, user_id=owner.id, role="owner")
    db.add(member)
    await db.commit()
    await db.refresh(household)
    return household


async def create_invite(
    db: AsyncSession, household: Household, invited_by: User, invited_email: str
) -> HouseholdInvite:
    invite = HouseholdInvite(
        household_id=household.id,
        invited_by=invited_by.id,
        invited_email=invited_email,
        token=str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def accept_invite(db: AsyncSession, token: str, user: User) -> HouseholdInvite:
    result = await db.execute(select(HouseholdInvite).where(HouseholdInvite.token == token))
    invite = result.scalar_one_or_none()
    if not invite or invite.expires_at < datetime.now(timezone.utc):
        raise ValueError("Invite not found or expired")
    if invite.accepted_at:
        raise ValueError("Invite already accepted")

    invite.accepted_at = datetime.now(timezone.utc)
    member = HouseholdMember(household_id=invite.household_id, user_id=user.id, role="member")
    db.add(member)
    await db.commit()
    await db.refresh(invite)
    return invite
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_households.py -v
```

Expected: All 3 tests `PASSED`.

- [ ] **Step 5: Create household schemas and router**

Create `backend/modules/households/schemas.py`:
```python
import uuid
from pydantic import BaseModel, EmailStr


class CreateHouseholdRequest(BaseModel):
    name: str
    type: str  # 'individual' | 'couple'


class InviteRequest(BaseModel):
    email: EmailStr


class HouseholdResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    model_config = {"from_attributes": True}
```

Create `backend/modules/households/router.py`:
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import User
from modules.households import service
from modules.households.schemas import CreateHouseholdRequest, HouseholdResponse, InviteRequest

# Two routers: one under /households, one at root for the invite accept link
router = APIRouter(prefix="/households", tags=["households"])
invite_router = APIRouter(tags=["households"])  # no prefix — produces /invite/{token}


@router.post("/", response_model=HouseholdResponse)
async def create_household(
    body: CreateHouseholdRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_household(db, current_user, body.name, body.type)


@router.post("/{household_id}/invite")
async def invite_partner(
    household_id: str,
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from modules.households.models import Household
    from sqlalchemy import select
    result = await db.execute(select(Household).where(Household.id == household_id))
    household = result.scalar_one_or_none()
    if not household:
        raise HTTPException(404, "Household not found")
    invite = await service.create_invite(db, household, current_user, body.email)
    # TODO Plan 2: enqueue invite email ARQ job
    return {"token": invite.token, "expires_at": invite.expires_at}


@invite_router.get("/invite/{token}")
async def accept_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partner clicks this link from their invite email to join the household."""
    invite = await service.accept_invite(db, token, current_user)
    return {"household_id": invite.household_id, "accepted_at": invite.accepted_at}
```

Register **both** routers in `main.py`:
```python
from modules.households.router import router as households_router, invite_router
app.include_router(households_router)
app.include_router(invite_router)  # produces GET /invite/{token}
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests `PASSED`.

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add household service with create, invite, and accept-invite"
```

---

### Task 7: Frontend Auth Pages

**Files:**
- Create: `frontend/app/lib/supabase/client.ts`
- Create: `frontend/app/lib/supabase/server.ts`
- Create: `frontend/app/(auth)/login/page.tsx`
- Create: `frontend/app/(auth)/onboarding/layout.tsx`
- Create: `frontend/app/(auth)/onboarding/connect-email/page.tsx`
- Create: `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx`
- Create: `frontend/app/(auth)/onboarding/setup-household/page.tsx`
- Create: `frontend/app/(auth)/onboarding/connect-bank/page.tsx`

- [ ] **Step 1: Create Supabase client utilities**

Create `frontend/app/lib/supabase/client.ts`:
```typescript
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

Create `frontend/app/lib/supabase/server.ts`:
```typescript
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll(),
        setAll: (cs) => cs.forEach(({ name, value, options }) =>
          cookieStore.set(name, value, options)
        ),
      },
    }
  );
}
```

- [ ] **Step 2: Create the Supabase OAuth callback route**

This is required by `@supabase/ssr` — without it, the OAuth redirect lands on a 404 and the session is never established.

Create `frontend/app/auth/callback/route.ts`:
```typescript
import { createClient } from "@/app/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");

  if (code) {
    const supabase = await createClient();
    await supabase.auth.exchangeCodeForSession(code);
  }

  // New users go to onboarding; existing users go to dashboard
  // (middleware will handle redirect based on session state in Plan 3)
  return NextResponse.redirect(`${origin}/onboarding/connect-email`);
}
```

- [ ] **Step 3: Create login page**

Create `frontend/app/(auth)/login/page.tsx`:
```typescript
"use client";
import { createClient } from "@/app/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const supabase = createClient();

  const signInWithGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        scopes: "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  const signInWithMicrosoft = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "azure",
      options: {
        scopes: "openid email profile Mail.Read",
        redirectTo: `${window.location.origin}/auth/callback`,
      },
    });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-luka-light">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold text-luka-primary">Luka</CardTitle>
          <p className="text-luka-muted mt-1">Finanzas personales y en pareja</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button onClick={signInWithGoogle} className="w-full bg-luka-primary hover:bg-blue-700">
            Continuar con Google (Gmail)
          </Button>
          <Button onClick={signInWithMicrosoft} variant="outline" className="w-full border-luka-primary text-luka-primary">
            Continuar con Microsoft (Outlook)
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Create onboarding layout with stepper**

Create `frontend/app/(auth)/onboarding/layout.tsx`:
```typescript
const STEPS = [
  { label: "Correo", href: "/onboarding/connect-email" },
  { label: "WhatsApp", href: "/onboarding/verify-whatsapp" },
  { label: "Hogar", href: "/onboarding/setup-household" },
  { label: "Banco", href: "/onboarding/connect-bank" },
];

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-luka-light flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-lg">
        <h1 className="text-2xl font-bold text-luka-primary text-center mb-2">Luka</h1>
        <div className="flex justify-center gap-2 mb-8">
          {STEPS.map((step, i) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-luka-primary text-white text-xs flex items-center justify-center font-bold">
                {i + 1}
              </div>
              <span className="text-sm text-luka-muted hidden sm:block">{step.label}</span>
              {i < STEPS.length - 1 && <div className="w-6 h-px bg-luka-primary/30" />}
            </div>
          ))}
        </div>
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create the 4 onboarding pages (shells)**

Create `frontend/app/(auth)/onboarding/connect-email/page.tsx`:
```typescript
"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

export default function ConnectEmailPage() {
  const router = useRouter();
  // Email already connected via OAuth — this page confirms provider and scope
  return (
    <Card>
      <CardHeader><CardTitle>Tu correo está conectado</CardTitle></CardHeader>
      <CardContent>
        <p className="text-luka-muted mb-4">
          Luka leerá solo los correos de alertas de tu banco para registrar tus gastos automáticamente.
        </p>
        <Button className="w-full bg-luka-primary" onClick={() => router.push("/onboarding/verify-whatsapp")}>
          Continuar →
        </Button>
      </CardContent>
    </Card>
  );
}
```

Create `frontend/app/(auth)/onboarding/verify-whatsapp/page.tsx`:
```typescript
"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

export default function VerifyWhatsAppPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [pinSent, setPinSent] = useState(false);

  const sendPin = async () => {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/whatsapp/send-pin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone }),
    });
    setPinSent(true);
  };

  const verifyPin = async () => {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/whatsapp/verify-pin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, pin }),
    });
    if (res.ok) router.push("/onboarding/setup-household");
  };

  return (
    <Card>
      <CardHeader><CardTitle>Verifica tu WhatsApp</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-luka-muted text-sm">
          Luka te enviará alertas de gastos por WhatsApp. Necesitamos verificar tu número.
        </p>
        <Input placeholder="+56 9 1234 5678" value={phone} onChange={e => setPhone(e.target.value)} />
        {!pinSent ? (
          <Button className="w-full bg-luka-primary" onClick={sendPin}>Enviar PIN por WhatsApp</Button>
        ) : (
          <>
            <Input placeholder="Código de 6 dígitos" value={pin} onChange={e => setPin(e.target.value)} />
            <Button className="w-full bg-luka-primary" onClick={verifyPin}>Verificar →</Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
```

Create `frontend/app/(auth)/onboarding/setup-household/page.tsx`:
```typescript
"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

export default function SetupHouseholdPage() {
  const router = useRouter();
  const [type, setType] = useState<"individual" | "couple" | null>(null);
  const [partnerEmail, setPartnerEmail] = useState("");

  const create = async () => {
    // Step 1: create the household
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/households`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Mi Hogar", type }),
    });
    const household = await res.json();

    // Step 2: send partner invite if couple type and email provided
    if (type === "couple" && partnerEmail && household.id) {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/households/${household.id}/invite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: partnerEmail }),
      });
    }

    router.push("/onboarding/connect-bank");
  };

  return (
    <Card>
      <CardHeader><CardTitle>¿Cómo usarás Luka?</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <Button variant={type === "individual" ? "default" : "outline"}
          className="w-full" onClick={() => setType("individual")}>
          Solo — quiero controlar mis gastos
        </Button>
        <Button variant={type === "couple" ? "default" : "outline"}
          className="w-full" onClick={() => setType("couple")}>
          En pareja — compartir con mi pareja
        </Button>
        {type === "couple" && (
          <Input placeholder="Email de tu pareja" value={partnerEmail}
            onChange={e => setPartnerEmail(e.target.value)} />
        )}
        {type && (
          <Button className="w-full bg-luka-primary" onClick={create}>Continuar →</Button>
        )}
      </CardContent>
    </Card>
  );
}
```

Create `frontend/app/(auth)/onboarding/connect-bank/page.tsx`:
```typescript
"use client";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "next/navigation";

const BANKS = ["Santander", "Banco de Chile", "BCI", "Scotiabank", "Itaú", "BICE", "Otro"];

export default function ConnectBankPage() {
  const router = useRouter();
  const [bank, setBank] = useState("");
  const [accountType, setAccountType] = useState<"personal" | "joint" | null>(null);

  const save = async () => {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/bank-accounts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bank_name: bank.toLowerCase(), account_type: accountType }),
    });
    router.push("/dashboard");
  };

  return (
    <Card>
      <CardHeader><CardTitle>Agrega tu banco</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <select className="w-full border rounded p-2 text-sm" value={bank} onChange={e => setBank(e.target.value)}>
          <option value="">Selecciona tu banco</option>
          {BANKS.map(b => <option key={b} value={b}>{b}</option>)}
        </select>
        <Button variant={accountType === "personal" ? "default" : "outline"}
          className="w-full" onClick={() => setAccountType("personal")}>
          Cuenta personal
        </Button>
        <Button variant={accountType === "joint" ? "default" : "outline"}
          className="w-full" onClick={() => setAccountType("joint")}>
          Cuenta conjunta (con tarjetas adicionales)
        </Button>
        {bank && accountType && (
          <Button className="w-full bg-luka-primary" onClick={save}>Ir al Dashboard →</Button>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 5: Verify frontend builds**

```bash
cd frontend
npm run build
```

Expected: Build succeeds, no type errors.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat: add auth login page and 4-step onboarding wizard"
```

---

## Chunk 4: Deployment Configuration

### File Map

```
luka/
├── backend/
│   └── Dockerfile
├── railway.toml
└── frontend/
    └── vercel.json
```

---

### Task 8: Railway + Vercel Deployment Config

- [ ] **Step 1: Create backend Dockerfile**

Create `backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create railway.toml**

Railway handles multi-service deployments via separate services in the Railway dashboard, each pointing to the same repo with different start commands. The `railway.toml` configures the **API service** only (the default deploy). The **worker service** is configured manually in the Railway dashboard as a second service from the same repo.

Create `railway.toml` at the monorepo root (for the API service):
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"

[deploy]
startCommand = "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

For the worker service — configure in Railway dashboard:
```
Service name: luka-worker
Root Directory: backend/
Build: same Dockerfile
Start command: python -m arq worker.WorkerSettings
```

> **Note:** Railway's `railway.toml` does not reliably support multi-service `[[services]]` blocks from a single config file. Use the dashboard for the second service.

- [ ] **Step 3: Create vercel.json for Next.js**

Create `frontend/vercel.json`:
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "devCommand": "npm run dev",
  "installCommand": "npm install",
  "env": {
    "NEXT_PUBLIC_API_URL": "@luka-api-url"
  }
}
```

- [ ] **Step 4: Set up Railway project**

```
1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select the Luka repo
3. Add Redis service: Railway dashboard → New → Redis
4. Set environment variables (from .env.example) in Railway dashboard
5. Railway auto-deploys on push to main
```

- [ ] **Step 5: Set up Vercel project**

```
1. Go to vercel.com → New Project → Import from GitHub
2. Select the Luka repo, set Root Directory to "frontend"
3. Add environment variables:
   NEXT_PUBLIC_SUPABASE_URL
   NEXT_PUBLIC_SUPABASE_ANON_KEY
   NEXT_PUBLIC_API_URL (Railway app URL)
4. Deploy
```

- [ ] **Step 6: Verify end-to-end deployment**

```bash
# Test Railway API
curl https://your-app.railway.app/health
# Expected: {"status": "ok", "app": "luka"}

# Test Vercel frontend
# Open https://your-app.vercel.app → should show Luka login page
```

- [ ] **Step 7: Final commit**

```bash
git add backend/Dockerfile railway.toml frontend/vercel.json
git commit -m "feat: add Railway and Vercel deployment configuration"
```

---

## Plan 1 Complete ✅

**What you now have:**
- Git monorepo with pre-commit secret scanning enforced
- FastAPI backend with health endpoint, config, async DB
- All 12 database tables migrated in Supabase
- Auth middleware (Supabase JWT → User)
- Household create, invite, and accept-invite flows
- Next.js frontend with Luka design system (blue palette)
- Login page (Google + Microsoft OAuth)
- 4-step onboarding wizard (email, WhatsApp, household, bank)
- Railway (API + worker + Redis) + Vercel deployment

**Next:** [Plan 2 — Transaction Pipeline](./2026-03-10-luka-plan-2-transaction-pipeline.md)
(Email webhooks, parser, merchant normalization + LLM, WhatsApp interactions, ARQ jobs)
