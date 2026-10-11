# FinSight AI

Personal finance intelligence platform: accounts, transactions, CSV import, budgets, goals, analytics,
recurring-expense and anomaly detection, generated insights, document RAG and a tool-calling AI assistant.
**All financial numbers are computed by backend services from PostgreSQL. The LLM only picks tools and explains
their output.** The whole finance core works with no AI configured.

## Features
- JWT auth (access + rotating refresh tokens, reuse detection), bcrypt hashing, roles (USER / ADMIN)
- Accounts, hierarchical categories, transactions (Decimal/NUMERIC money, filters, search, sort, pagination)
- CSV import via Celery: header auto-detection + custom mapping, debit/credit columns, DB-enforced de-duplication, progress polling
- Rule-based categorisation first, LLM only for unresolved rows
- SQL-aggregated analytics, budgets (usage, projected spend, warnings), goals (required contribution, projection)
- Recurring detection (interval + amount regularity), anomaly detection (SQL baselines + z-score)
- Scheduled insights (deduplicated), live notifications
- AI assistant: provider abstraction (OpenAI-compatible, Anthropic), 14 safe tools, conversation memory,
  unsupported-number detector, deterministic rule-router fallback
- RAG: upload txt/md/pdf → chunk → embed → pgvector (HNSW, cosine) with per-user isolation
- Observability: JSON logs with request id, Prometheus `/metrics`, `/health`, `/ready`; Redis rate limiting
- React + TypeScript + Vite dashboard (charts, import, budgets, goals, insights, assistant)

## Architecture
```
React ──► Nginx ──► FastAPI ──► Services ──► PostgreSQL (+pgvector)
                       │            ▲
                       │            └──── AI tools (fixed, validated, user-scoped)
                       ├──► Redis ◄── Celery worker / beat (imports, categorisation, embeddings, detection, insights)
                       └──► AI orchestrator ──► LLMProvider (OpenAI-compatible | Anthropic | none → rule router)
```
Key decisions
- **Services own the logic**; routes are thin; Celery tasks only orchestrate services.
- **Money**: `Decimal` in Python, `NUMERIC(14,2)` in PostgreSQL. Decimals become JSON numbers only at the response boundary.
- **Tenant isolation**: every query filters by `user_id`; foreign rows answer 404; vector search filters on a denormalised `user_id`.
- **Sync SQLModel sessions** run in FastAPI's threadpool (no blocking of the event loop); `async` is used where I/O is
  awaited (LLM / embedding HTTP calls, `/ai/*`).
- **Dedup** is a unique constraint `(user_id, fingerprint)` + `INSERT … ON CONFLICT DO NOTHING`; identical rows inside one file are kept via an occurrence counter.
- **No `create_all()`** outside tests; schema = Alembic. `migrations/env.py` imports every model and creates the `vector` extension.
- Embeddings default to a local hashing embedder (lexical, zero dependencies). Set `EMBEDDING_PROVIDER=openai` for semantic search
  (keep `EMBEDDING_DIM` equal to the DB column; changing it needs a new migration).

## Tech stack
Python 3.12+, FastAPI, Pydantic v2, SQLModel/SQLAlchemy 2, Alembic, PostgreSQL 16 + pgvector, psycopg 3, Redis, Celery, pandas,
pypdf, httpx, prometheus-client, pytest; React 18, TypeScript, Vite, Recharts; Docker, Nginx.

## Project structure
`app/api` routes · `app/services` business logic · `app/ai` provider, tools, orchestrator, RAG · `app/workers` Celery ·
`app/db/models` tables · `app/schemas` API models · `app/utils` money/dates/csv/validators · `migrations` Alembic ·
`tests/{unit,integration,api}` · `frontend` React app · `docker` Nginx + Postgres init · `scripts/seed.py` demo data.

## Environment variables
Copy `.env.example` to `.env` (the setup script does this and generates `JWT_SECRET_KEY`). Never commit `.env`.
| Variable | Purpose |
|---|---|
| `DATABASE_URL`, `REDIS_URL` | Host URLs for local runs. Docker Compose overrides them with service names. |
| `JWT_SECRET_KEY` (≥32 chars in production), `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Auth |
| `LLM_PROVIDER` (`openai`\|`anthropic`\|empty), `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | Assistant model. Empty = rule router. |
| `EMBEDDING_PROVIDER`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_BASE_URL`, `EMBEDDING_DIM` | RAG embeddings |
| `CORS_ORIGINS`, `MAX_UPLOAD_SIZE_MB`, `UPLOAD_DIR` | Web / uploads |
| `RATE_LIMIT_ENABLED`, `RATE_LIMIT_AI_PER_MINUTE`, `RATE_LIMIT_UPLOAD_PER_MINUTE` | Per-user limits |
| `CELERY_EAGER` | Run tasks inline (no worker needed; used by tests) |

## Local development
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d postgres redis      # PostgreSQL+pgvector and Redis
alembic upgrade head
python -m scripts.seed                   # optional demo data: demo@finsight.dev / Demo@12345
uvicorn app.main:app --reload            # http://localhost:8000/docs
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
cd frontend && npm install && npm run dev   # http://localhost:5173
```
Without a Celery worker set `CELERY_EAGER=true` in `.env` and uploads/detections run inline.

## Docker
```bash
docker compose up -d --build            # full stack behind Nginx on http://localhost
docker compose logs -f backend
docker compose logs -f celery_worker
docker compose down                     # add -v to also drop the database volume
```
Services: postgres (pgvector), redis, backend (runs `alembic upgrade head` on start), celery_worker, celery_beat, frontend, nginx.
The backend, worker and beat share an `uploads` volume.

## Database migrations
```bash
alembic revision --autogenerate -m "describe change"   # ALWAYS review the generated file
alembic upgrade head
alembic check                                          # models and DB in sync?
```
The initial migration was generated by the setup script; review `migrations/versions/*` before deploying.

## Testing
```bash
pytest                      # unit tests always run; DB tests need PostgreSQL+pgvector
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/finsight_test pytest -v
ruff check .
```
The LLM is never called in tests (rule router or an in-process fake provider). Covered: money, dates, validators, categorisation,
budget maths, anomaly + recurring detection, CSV parsing, AI tools (argument validation, selection, provider failure, missing data),
import idempotency, analytics, auth flows and **cross-user isolation** (accounts, transactions, documents, conversations).

## API documentation
Swagger UI `/docs`, ReDoc `/redoc`, schema `/openapi.json`. Errors always look like
`{"error": {"code": "TRANSACTION_NOT_FOUND", "message": "Transaction not found."}}`.
Main groups: Authentication, Users, Accounts, Categories, Transactions, Imports, Budgets, Goals, Analytics, Insights, AI, Documents (all under `/api/v1`).

Quick try:
```bash
curl -s localhost:8000/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"demo@finsight.dev","password":"Demo@12345"}'
curl -s localhost:8000/api/v1/ai/ask -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"question":"How much did I spend on food last month?"}'
```

## AI architecture
1. `POST /ai/ask` → orchestrator loads conversation history (context only).
2. With a provider: the model receives the tool list and may call tools (max 5 rounds, 4 calls per round). Without one, or on provider failure, a deterministic router maps the question to tools and renders the answer itself.
3. Tools (`get_transactions`, `get_transaction`, `get_monthly_summary`, `get_category_expenses`, `get_category_trends`, `get_income_summary`, `get_cashflow`, `compare_months`, `get_budget_status`, `get_goal_status`, `get_recurring_expenses`, `get_anomalies`, `get_top_merchants`, `search_documents`) are parameterised Python functions. `user_id` comes from the authenticated request, never from model output; argument models forbid extra keys; the model can never run SQL.
4. Tool errors are returned to the model as data so it can retry; unknown tools / invalid arguments are never executed.
5. The response carries `tools_used`, the raw `data`, `source` (`llm`/`rules`), a disclaimer, and `unverified_numbers` (numbers in the prose that appear in no tool result).

## RAG architecture
Upload → validate → store → Celery `generate_embeddings` → extract (txt/md/pdf) → clean → paragraph-aware chunks (~900 chars, overlap)
→ embed → `document_chunks.embedding vector(EMBEDDING_DIM)` with an HNSW cosine index. Query → embed → cosine search filtered by
`user_id` and `READY` documents → top-k chunks (`/ai/search`, or the `search_documents` tool).

## Security
Hashed passwords (SHA-256 pre-hash + bcrypt), short-lived access tokens, rotating refresh tokens stored hashed with reuse detection,
login brute-force limiter, per-user rate limits (AI, uploads), strict CORS, extension/size/binary checks and generated storage names for
uploads, parameterised SQL only, ownership checks on every resource, secrets only via environment, logs never contain passwords,
tokens or API keys, stack traces hidden outside `DEBUG`, `/metrics` not exposed through Nginx.
Treat document text as untrusted: the system prompt tells the model to ignore instructions inside tool results.

## Deployment notes
- Set `APP_ENV=production`, a random `JWT_SECRET_KEY` (≥32 chars), `DEBUG=false`, a strong DB password, restrictive `CORS_ORIGINS`.
- Terminate TLS in front of Nginx (or add a TLS server block); run backend replicas behind it; one Celery beat instance only.
- Back up the `pgdata` volume; run `alembic upgrade head` as a release step.
- Scrape `/metrics` from inside the network (HTTP latency/errors, AI latency/outcomes, tool calls, DB errors, Celery failures).

## Future improvements
Bank/UPI aggregator connectors (none exist today – the app never claims bank connectivity), Isolation-Forest anomaly model,
multi-currency conversion, shared household accounts, e-mail/push alerts, OCR for scanned statements, streaming assistant responses,
async SQLAlchemy engine, OpenTelemetry tracing.
