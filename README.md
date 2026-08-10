# ClauseBridge

AI-assisted legal document diligence tool. Upload contracts, NDAs, leases, employment agreements; the system classifies each document, extracts key clauses into a structured table, and flags clauses that look unusual versus the firm's own standard templates — every flag traceable to a source sentence with a confidence score.

## Status

Under active development. Phase 0 (bootstrap) in progress.

## Repository layout

```
apps/
  web/     Next.js 14 frontend
  api/     FastAPI backend
infra/     Docker Compose for local dev
docs/      Architecture + API reference
```

## Running locally

Not yet available — Docker Compose stack (postgres, redis, api, worker, web) is added in Phase 1.

## License

See LICENSE.