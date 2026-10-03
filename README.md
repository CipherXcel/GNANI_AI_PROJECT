# Suno — Audio Notes

Existing Gnani Audio Notes project: Next.js, FastAPI, PostgreSQL and an independent worker. Audio is stored in **real private AWS S3 in both local development and production**. The worker keeps the existing 30-second Gnani REST section pipeline and saves each section before Gemini summarization.

## Local startup (Windows)

Install Docker Desktop (Linux containers). Node 22+ is needed only for host frontend tooling/tests. Copy `.env.example` to `.env` only for a new installation; retain existing secrets and database values on this machine.

Set `POSTGRES_PASSWORD`, `SESSION_SECRET`, `AWS_REGION`, `S3_BUCKET`, `GNANI_API_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`. Compose derives the database URL using `postgres:5432`. S3 must be provisioned privately with CORS allowing `http://localhost:3000` (see `deploy/s3-cors.json`).

Choose one AWS credential source:

- Standard `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and optional `AWS_SESSION_TOKEN` in ignored `.env`.
- Your normal host AWS profile: set `AWS_CONFIG_DIR=C:/Users/YOUR_USER/.aws` and `AWS_PROFILE=default` in `.env`. The helper adds the read-only profile mount. SSO profiles must be logged in on the host first; the app container does not write to the profile directory.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-dev.ps1 -Build
```

Or run explicitly (profile variant):

```powershell
docker compose -f docker-compose.yml -f docker-compose.aws-profile.yml up -d --build
```

For credentials in `.env`, omit the second `-f`. The frontend uses `/api/...`; its server proxy connects to `backend:8000`. Open **http://localhost:3000**, matching `APP_ORIGIN`.

| Local service | Address |
|---|---|
| Frontend / architecture | http://localhost:3000 /architecture |
| FastAPI / health | http://localhost:8000/docs /health |
| PostgreSQL (local tooling only) | localhost:5433 |
| Original audio | Private AWS S3 signed URLs |

On this machine, another project occupies 3000/8000, so the ignored `.env` selects **http://localhost:3100** and API port **8100**. Optional `FRONTEND_PORT`, `BACKEND_PORT`, `POSTGRES_PORT` override host bindings only; container service ports stay 3000/8000/5432. Match `APP_ORIGIN` and bucket CORS to the selected frontend port. Set `$env:TEST_BASE_URL="http://localhost:3100"` before browser tests on this machine.

All local host ports bind to loopback. PostgreSQL uses the existing `gnani-audio-notes_postgres_data` volume. `docker compose down` preserves it; **do not use `down -v`**. Stopping the browser after a completed upload does not stop processing.

```powershell
docker compose logs -f backend worker
docker compose ps
docker compose restart worker
```

For hot frontend editing, stop its container, then run `npm ci` in `frontend` and `$env:BACKEND_URL='http://127.0.0.1:8000'; npm run dev`. The loopback URL is a host development setting only; containers use Docker service names.

## Features

- Drag-and-drop audio uploads, validated type/size, language selection, actual byte progress, bounded multipart retries, and cancellation.
- English and nine Indian language choices supported by Gnani REST.
- Background transcription of long recordings using 30-second sections with 1-second overlap.
- Saved chunk checkpoints and durable jobs; crashed workers can be replaced and expired leases recovered.
- Structured Gemini overview, key takeaways, topics, and explicit action items.
- Saved recording library with search, status filters, list/grid views, rename, and confirmed deletion.
- Audio playback, speed controls, timestamp seeking, searchable transcripts, copy, and TXT/Markdown/SRT/JSON export.
- Useful empty, loading, processing, disconnected, and failed states. A failed summary preserves the complete transcript.
- Browser-specific private workspaces with signed HttpOnly cookies and per-record authorization.
- Responsive interface, keyboard-accessible dialogs and tabs, reduced-motion support, and an `/architecture` explanation.

## Flow and data model

```text
Next.js browser → FastAPI upload session → signed multipart PUTs → private S3 bucket
                         ↓ complete & validate
              PostgreSQL: note + job in one transaction
                         ↓ worker claim + renewable lease
        download original → FFprobe → FFmpeg 30s sections → Gnani
                         ↓ checkpoint each transcript section
           save full transcript → Gemini map/reduce summary → ready
                         ↓
                  browser polls saved progress
```

`notes` contains metadata, progress, transcript and summary; `segments` contains chunk transcripts and approximate times; `jobs` implements the durable queue; `worker_heartbeats` indicates whether a worker is online. The queue uses PostgreSQL `FOR UPDATE SKIP LOCKED`, 180-second leases and 15-second heartbeats. Ownership is checked before each checkpoint. A retry after an LLM error uses the saved transcript without invoking ASR again.

Alembic runs as a one-shot migration service before the API starts. The operator provisions private AWS S3, browser CORS and a one-day incomplete-multipart cleanup rule. The API does not need bucket-administration permissions. The worker starts only after the API is healthy.

## Key files

| File | Responsibility |
|---|---|
| `frontend/app/page.tsx` | Library, search, filters and upload entry point |
| `frontend/components/upload-dialog.tsx` | Multipart upload and byte progress |
| `frontend/components/note-reader.tsx` | Playback, transcript, summary and export |
| `frontend/app/api/[...path]/route.ts` | Same-origin proxy to FastAPI; no provider keys |
| `backend/app/api.py` | API routes, ownership checks, upload finalization |
| `backend/app/worker.py` | Durable queue claims, leases, checkpoints and processing |
| `backend/app/audio.py` | Audio validation, segmentation and boundary deduplication |
| `backend/app/providers.py` | Gnani/Gemini requests, retries and summary validation |
| `backend/app/models.py` | SQLAlchemy data model |
| `backend/app/storage.py` | AWS default credential chain and private signed URLs |
| `backend/tests/test_pipeline.py` | Critical integration and failure-path tests |


## Automated verification

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test.ps1
cd frontend
npm run test:ui
```

Backend tests use a separate local PostgreSQL database ending in `_test`, real FFmpeg and in-process Moto S3 mocks. No AWS or AI provider calls are made. They cover workspace isolation, multipart integrity/idempotency, provider retries, corrupt audio, saved transcripts, lease recovery and interruption after a saved chunk. Frontend checks include TypeScript, ESLint, production build and desktop/tablet/mobile Playwright regression tests with API fixtures. Browser tests require the local frontend at port 3000 and Microsoft Edge (or install Playwright Chromium and set `PLAYWRIGHT_CHANNEL=chromium`). Tests do not need a private user's browser cookie.

Live provider checks are separate and use credits:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\generate-test-audio.ps1
node scripts/e2e.mjs
```

`node scripts/e2e.mjs --resume` retries a saved failed recording without retranscribing saved sections. Runtime cookies, audio and results stay under ignored `.runtime/`. Do not share them. `scripts/ui-smoke.cjs` remains available for the original real-recording smoke workflow.

## EC2 deployment

Follow [DEPLOY_EC2.md](DEPLOY_EC2.md). One EC2 runs Caddy, frontend, backend, worker and PostgreSQL. Only Caddy exposes 80/443. Production uses an EC2 IAM role, private AWS S3 and secure same-origin cookies. Docker Compose files are independently runnable; do not layer the development Compose file into production.

## Operational limits

The default upload limit is 50 GiB; choose a smaller `MAX_UPLOAD_BYTES` if the worker disk cannot hold the original plus a temporary WAV chunk. Original playback depends on browser codec support. Section timestamps are approximate, not word-level subtitles. Workspace access depends on the HttpOnly browser cookie and stable `SESSION_SECRET`; clearing cookies loses access. Anonymous workspaces are not accounts or a complete abuse-prevention system. A small public demo needs a controlled audience/provider budget. Persistent volumes need separate backups. See [VERIFICATION.md](VERIFICATION.md) for actual executed checks and remaining live gates.

Provider references: [Gnani STT](https://docs.gnani.ai/api/STT/speech-to-text), [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output).
