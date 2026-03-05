# Architect Output — Web Deployment Requirements

**Date**: 2026-03-04
**Sequence**: 01
**Context**: architect
**Description**: web-deployment-requirements
**Project**: devotional-generator-system-a

---

## Summary

Analysis of implementation requirements to safely move the Devotional Generator from a local-only application to a web-deployed application. Requirements are organized by layer and prioritized for incremental migration.

---

## 1. Authentication & Authorization

**Current state:** Single operator, no auth — localhost only.

**Web requirement:**
- OAuth2/OIDC provider (Auth0, Clerk, or self-hosted) for operator login
- JWT session tokens with short expiry + refresh token rotation
- Route-level middleware on FastAPI: every API endpoint requires a valid session
- Role model (at minimum: `operator` — the human reviewer/approver)
- If multi-user ever added: row-level security on all data tables by `user_id`

---

## 2. Secrets & Key Management

**Current state:** macOS Keychain (`security` framework) — not available on any server OS.

**Web requirement:**
- Replace macOS Keychain with a cloud KMS: AWS KMS, GCP Cloud KMS, or HashiCorp Vault
- All secrets (LLM API keys, Bolls.life, API.Bible, DB passwords) injected via environment at runtime — never in code or config files
- The `src/security/encryption.py` abstraction already anticipates swappable key backends — the cloud KMS becomes the new primary; passphrase fallback demoted to recovery-only
- Audit log every key access event

---

## 3. Database

**Current state:** SQLite — single-writer, file-based, no concurrent connections.

**Web requirement:**
- Postgres with connection pooling (PgBouncer or SQLAlchemy `pool_size`/`max_overflow`)
- The database socket migration plan (`__04__`–`__07__` documents) already specifies the `PostgresAdapter` — this work becomes the critical path for web deployment
- The single-active-provider constraint (partial unique index on `state = 'active'`) specified in the migration plan for Postgres must be implemented
- TLS required on all Postgres connections — already specified in migration plan §7

---

## 4. Vector Store (RAG)

**Current state:** ChromaDB running against local files.

**Web requirement:**
- Hosted vector database: Qdrant Cloud, Pinecone, Weaviate, or `pgvector` as a Postgres extension (simplest — same DB instance)
- The `QuoteRAGInterface` / `ExpositionRAGInterface` Protocol contracts mean the swap is contained — only the adapter changes
- Index population (`src/rag/setup.py`) becomes a one-time admin job, not a local script

---

## 5. File & PDF Storage

**Current state:** Local filesystem — workspace files, ChromaDB data dir, exported PDFs.

**Web requirement:**
- Object storage: S3, GCS, or Azure Blob for all generated content
- PDFs delivered as **signed, time-limited URLs** (not direct file paths) — prevents unauthorized access to exported devotional books
- Workspace files and registry backup also go to object storage with server-side encryption
- Local `Path` references in the codebase get abstracted behind a `StorageBackend` protocol (mirrors the `DatabaseSocket` pattern)

---

## 6. Long-Running Job Queue

**Current state:** Generation pipeline runs synchronously inline — fine for a local CLI, fatal for a web server (request timeout, no feedback loop).

**Web requirement:**
- Async job queue for all long-running operations:
  - Devotional generation (LLM calls, multi-section pipeline)
  - RAG retrieval and grounding map production
  - PDF export (TypeScript subprocess call)
  - RAG index setup/refresh
- Implementation options: Celery + Redis, or BullMQ (Node.js side for the TypeScript worker)
- FastAPI endpoint returns `job_id` immediately; client polls status endpoint or receives webhook/SSE when done
- The Review UI's `client.ts` needs to handle async polling — current synchronous API design would need extending

---

## 7. Python–TypeScript Integration

**Current state:** Python spawns a TypeScript subprocess (Option A from Phase 003) — works locally, problematic at scale.

**Web requirement:**
- Switch to **Option B** (TypeScript micro-service): a small Node.js server running the PDF engine on a fixed internal port
- Python calls it via HTTP internally (not public-facing)
- Or: move PDF generation to the job queue — worker calls the TypeScript service asynchronously
- Containerize both processes together (same pod/task) with internal networking

---

## 8. API Security

These are absent on localhost, required for any web exposure:

- **HTTPS/TLS** — terminate at load balancer (NGINX, Cloudflare, ALB)
- **CORS** — restrict `allowed_origins` to the exact web domain; remove `*`
- **CSRF protection** — required for any state-changing form operations in the Review UI
- **Rate limiting** — on all API endpoints, especially LLM-triggering routes; prevents cost runaway
- **Input size limits** — FastAPI `Body(max_length=...)` on all text inputs; Pydantic validation already present but web surface is larger
- **Security headers** — `Content-Security-Policy`, `X-Frame-Options`, `Strict-Transport-Security` on all responses

---

## 9. LLM API Cost & Safety Controls

**Current state:** Operator runs one generation at a time locally — no runaway risk.

**Web requirement:**
- Per-session or per-user LLM spend caps
- Server-side token counting before dispatch — reject oversized prompts
- Circuit breaker on the LLM client: stop retrying on repeated provider errors; surface the error cleanly
- API key rotation without downtime (handled by secrets manager)

---

## 10. Observability

Not needed locally; required for diagnosing production issues:

- **Structured logging** — all generation pipeline steps emit JSON logs with `job_id`, `session_id`, `step`, `outcome`; no plain `print()` statements
- **Distributed tracing** — OpenTelemetry spans across the Python API, TypeScript PDF service, RAG calls, and LLM calls; correlated by `job_id`
- **Metrics** — generation success rate, LLM latency, PDF export latency, AC harness pass/fail rates
- **Alerting** — LLM error spikes, queue depth thresholds, export gate blocking rate

---

## 11. Content & Data Isolation

The system handles theologically sensitive, operator-approved content. For web:

- All generated devotional content scoped to the authenticated operator — no cross-user data access possible at the DB query level (row-level security)
- The export gate check (publish-ready mode requires all sections approved) remains mandatory on the server side — cannot be bypassed by a UI call
- Grounding Maps and Prayer Trace Maps contain retrieved theological source excerpts — not exposed publicly; operator-only review artifacts
- AC Scoring Harness output (pass/fail for all 43 ACs) is a competition artifact — store encrypted in object storage

---

## 12. Containerization & Deployment

- Dockerfile for the Python FastAPI app
- Dockerfile for the TypeScript PDF service
- `docker-compose` or Kubernetes manifests for local dev parity
- Health check endpoints (`/healthz`, `/readyz`) on both services
- Graceful shutdown handling: drain in-flight requests, close DB connections cleanly
- DB migrations via Alembic (already listed as a dependency in the migration plan) run as an init container or pre-deploy job — never on application startup

---

## Incremental Migration Priority Order

| Priority | Area | Blocking reason |
|---|---|---|
| 1 | Authentication | Nothing else is safe without this |
| 2 | Postgres + database socket | SQLite cannot serve concurrent web requests |
| 3 | Secrets / KMS | macOS Keychain is hard-blocked on any server OS |
| 4 | Job queue | Generation pipeline blocks HTTP workers without this |
| 5 | HTTPS + API security headers | Required before any public URL |
| 6 | File / PDF storage | Replace local paths with object storage |
| 7 | Rate limiting + LLM cost controls | Prevents runaway spend |
| 8 | Vector store migration | ChromaDB local files don't work in a replicated deployment |
| 9 | Observability | Required to operate reliably once live |
| 10 | TypeScript micro-service | Subprocess approach fails under load |

---

## Dependency Notes

- Items 2 (Postgres) and 3 (Secrets/KMS) are prerequisites for item 7 (File storage) and item 8 (Vector store) — all require a server-safe credential and connection strategy before those adapters can be written.
- Item 4 (Job queue) requires item 2 (Postgres) for job state persistence if using a DB-backed queue.
- Item 12 (Containerization) should be done in parallel with items 1–4 to ensure local dev parity from the start.
- The `DatabaseSocket` / provider-adapter pattern already designed in the migration plan (`__04__`–`__07__`) is the correct architectural foundation for items 2 and 8 — completing that work first minimizes rework.

---

*Output artifact created. Not a planning phase artifact — informational architecture reference for future web deployment phase.*
