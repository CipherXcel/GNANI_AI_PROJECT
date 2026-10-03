# Gnani Audio Notes

A private browser workspace for uploading audio, viewing transcription progress, reading a saved transcript and English AI notes, and reopening previous results. Audio playback, copy controls, checkpoint-aware retry and a public /architecture page complete the workflow.

## Stack and execution

Next.js App Router, React, TypeScript and CSS Modules serve the frontend. FastAPI handles request-bound API operations. PostgreSQL stores ownership, metadata, results and durable action checkpoints. Private S3 stores original audio and derived playback/long-audio inputs. One independent Python worker in the same backend codebase calls Gnani Batch and Gemini.

No Redis, Celery, WebSockets, microservices or login system are required. The worker runs as a separate OS process; restarting FastAPI does not discard accepted work. A PostgreSQL session guard admits one worker and short generation-token claims protect writes after external I/O.

## Workflow

1. Choose audio and a supported Batch language, default English (India).
2. Browser sends bounded multipart parts directly to private S3.
3. API verifies and completes the original and transactionally creates one application job.
4. Worker validates/decodes audio and prepares MP3 playback.
5. Gnani Batch creates, starts, polls and provides transcript JSON; provider-sized audio uses the original object.
6. Audio over four hours is split in order into at most 3h50m inputs.
7. Complete transcript is committed before Gemini.
8. Gemini generates validated English notes with ordered checkpointed reductions when needed.
9. Browser polls lightweight state and fetches results only when their timestamps change.

Progress separates transferred bytes, application stage and last Gnani observation. Transcription has no fabricated percentage/ETA. Summary failure leaves the transcript accessible. An unknown create response is held for operator reconciliation to avoid blind duplicate charges.

## Run locally on Windows

The complete project has been materialized from [the implementation manual](IMPLEMENTATION_CODEBOOK.md), preserving [the approved blueprint](MASTER_PROJECT_BLUEPRINT.md). Local dependencies, separate development/test PostgreSQL databases and migrations are prepared. See the [implementation report](docs/implementation-report.md) for executed checks, implementation fixes and remaining external-service gates.

Use Python 3.12, Node 24 LTS, PostgreSQL 18 and FFmpeg. Follow [environment setup](docs/environment.md) for the prepared Windows launch commands or setup on another machine. This workspace uses API port 8001 because Docker already occupies 8000; the browser still uses http://localhost:3000 and relative /api requests.

Run API, worker and frontend in separate terminals. Open http://localhost:3000. Keep backend credentials server-side; frontend has only a public repository URL and development rewrite origin. Examples contain values you must replace.

## Tests and verification

Run pytest against the explicitly isolated local gnani_audio_test database. Frontend checks are typecheck, lint, build, Vitest and Playwright. See [verification](docs/verification.md) and [provider smoke evidence](docs/provider-smoke-notes.md). Mocked tests do not prove provider access, actual S3 signatures, runtime performance or deployment; execute the real smoke gates.

## Privacy, limits and reliability

History belongs to a signed HttpOnly browser cookie, not a user account. Clearing cookies, changing browser or expiry starts an empty workspace; old records follow retention. Upload ownership is always checked before signing. CSRF and exact Origin protect mutations. Signed URLs are temporary bearer capabilities; never share them.

Application envelope: up to 2 GiB and 24 hours; provider per-input duration at most four hours and detected speech segment limit 5,000. Supported single-language Batch codes: bn-IN, en-IN, hi-IN, kn-IN, ml-IN, mr-IN, ta-IN, te-IN. Summary language is English. Unsupported/corrupted media is rejected.

Audio/playback lasts 30 days; saved text 90 days, with active/uncertain work protected. Summary-only retry can use a saved transcript after audio retirement. Automatic action retries are bounded; manual pipeline executions are bounded separately. External exactly-once billing is not promised.

## Deployment

The initial deployment uses one EC2 instance with Caddy TLS, separately supervised Next/API/worker processes, PostgreSQL on an encrypted persistent data volume, private S3 and daily database backups. Follow [production runbook](docs/runbook.md). Only public 80/443 and restricted SSH are exposed. One host remains an availability limitation.

Restore blocks all mutations and requires reconciliation of stale pending/active checkpoints before resuming automatic work. Backups are only useful after a tested restore drill.

## Evaluation

The public /architecture page explains storage, upload/transcription flow, long audio, request-bound/background operations, progress, failure handling and trade-offs. Set the actual GitHub repository URL before the production build. Follow the final submission checklist in verification.md; no live success, public URL or receipt is invented in this README.
