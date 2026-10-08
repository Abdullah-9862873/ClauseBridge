# ClauseBridge

AI-assisted legal document diligence tool. Upload contracts, NDAs, leases, employment agreements; the system classifies each document, extracts key clauses into a structured table, and flags clauses that look unusual versus country law, the firm's own standards, or uploaded reference documents — every flag traceable to a source sentence with a confidence score.

## Status

Under active development. Core pipeline (upload → classify → extract → anomaly detection → review) is functional. Docker Compose stack and fuller docs are not yet in place.

## Repository layout

```
apps/
  backend/    FastAPI + Celery API (Python 3.12+)
  frontend/   Next.js 16 App Router UI (React 19)
docs/         Architecture + API reference (planned)
infra/        Docker Compose for local dev (planned)
```

The two apps are independent — there is no root workspace tooling. Run them separately.

## Stack

**Backend** (`apps/backend`)

- FastAPI + Uvicorn, async SQLAlchemy + asyncpg
- PostgreSQL with pgvector (clause & reference-chunk embeddings, 384-d MiniLM)
- Celery + Redis (background document processing, broker)
- Groq LLM (`openai/gpt-oss-120b`) for classification, clause extraction, anomaly detection, prompt-injection checks
- Supabase S3-compatible storage for PDFs
- Alembic migrations, pytest + ruff + mypy (strict)

**Frontend** (`apps/frontend`)

- Next.js 16 (App Router), React 19, TypeScript
- TanStack Query, Tailwind CSS v4, react-pdf
- Vitest + Testing Library

## Prerequisites

- Python 3.12+ and Node.js 18+
- A PostgreSQL database with the `vector` extension (e.g. Supabase)
- Redis
- Groq API key
- S3-compatible object storage (e.g. Supabase Storage)

## Environment

Copy `apps/backend/.env.example` to `apps/backend/.env` and fill in every value. Required variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://…`) |
| `JWT_SECRET` | Secret for signing access/refresh tokens |
| `SUPABASE_STORAGE_ACCESS_KEY` | Object-storage access key |
| `SUPABASE_STORAGE_SECRET` | Object-storage secret |
| `SUPABASE_STORAGE_ENDPOINT` | S3 endpoint URL |
| `SUPABASE_STORAGE_BUCKET` | Bucket name |
| `REDIS_URL` | Redis connection string |
| `GROQ_API_KEY` | Groq API key |
| `LLM_PROVIDER` | LLM provider name (e.g. `groq`) |
| `CACHE_TTL_SECONDS` | Redis cache TTL |

Frontend reads optional `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

## Running locally

### Backend

```bash
cd apps/backend
python -m venv .venv
# Windows: .venv\Scripts\activate | Unix: source .venv/bin/activate
pip install -e .
alembic upgrade head          # apply migrations (creates tables + pgvector extension)
uvicorn main:app --reload --port 8000
```

In a second terminal, start the Celery worker (required for document processing):

```bash
cd apps/backend
# activate the venv first
celery -A workers.celery_app.celery_app worker --loglevel=info
```

API base: `http://localhost:8000` · health: `GET /api/v1/health` · interactive docs: `/docs`

### Frontend

```bash
cd apps/frontend
npm install
npm run dev
```

UI: `http://localhost:3000` (CORS is configured for this origin).

## How it works

1. Sign up creates a firm + admin user; log in to get JWT access (15 min) + refresh (7 day) tokens.
2. Create a case, optionally set a country (drives country-law anomaly checks) and upload reference PDFs (embedded into a per-case vector cache for RAG-style matching).
3. Upload a contract PDF (idempotency-key protected). A Celery worker:
   - extracts text (pypdf) and dedupes by content hash
   - runs a prompt-injection check
   - classifies the document type via LLM
   - extracts clauses and embeds them (MiniLM, 384-d)
   - detects anomalies at clause level (country law / firm standard), document level (country law), and against reference documents (top-5 cosine ≥ 0.3)
4. Review clauses and anomalies in the split PDF viewer: search, filter by severity, mark reviewed, jump to page.
5. Download a per-case PDF report of findings.

## API surface (v1)

Mounted under `/api/v1`: `auth`, `firms`, `cases`, `documents`, `reference-documents`, `clauses`, `anomalies`, `dashboard`, `queue`. See `GET /docs` when the server is running for the full OpenAPI schema.

## Testing

```bash
# Backend (from apps/backend, venv active)
pytest

# Frontend (from apps/frontend)
npm run test:run
npm run lint
```

## Notes

- Case deletion wipes related anomalies, clauses, documents, reference data, and the Redis LLM cache for that workload.
- PDF viewing authenticates via a short-lived token query parameter (set by the frontend); other API calls use the `Authorization: Bearer` header.
- There is no Docker Compose or CI yet; `docs/` and `infra/` are placeholders.

## License

No license file is present yet.
