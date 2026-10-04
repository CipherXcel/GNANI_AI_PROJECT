# Gnani Audio Notes

A full-stack audio processing platform that converts uploaded recordings into searchable transcripts and structured AI notes using **Gnani ASR** and **Gemini**.

🌐 **Live Application:** https://notes.cipherxcel.app  
🏗️ **Architecture:** https://notes.cipherxcel.app/architecture  
💻 **GitHub:** https://github.com/CipherXcel/GNANI_AI_PROJECT

---

## Overview

Gnani Audio Notes allows users to upload audio recordings, store them securely in AWS S3, transcribe them with Gnani ASR, generate structured notes using Gemini, and revisit previous recordings from a searchable library.

The application separates file transfer, API requests, and long-running AI processing.

Large audio files are uploaded directly from the browser to private AWS S3 using multipart presigned URLs instead of passing through the application server.

Transcription and summarization run asynchronously in a separate background worker using PostgreSQL-backed durable job state.

---

## Core Features

- Audio upload with progress tracking
- Direct browser-to-AWS-S3 multipart upload
- Private AWS S3 object storage
- Short-lived presigned upload and playback URLs
- Upload retries
- Background audio processing
- Gnani ASR transcription
- Chunked transcription for longer audio
- Persisted transcript progress
- Structured Gemini summaries
- Recording library/history
- Search and filtering
- Audio playback
- Playback speed controls
- Timestamped transcript navigation
- Rename and delete
- Export support
- Processing and error states
- Responsive frontend
- Production HTTPS deployment

---

## Production Architecture

```text
                         User
                          │
                        HTTPS
                          │
                          ▼
                       Caddy
                          │
                   AWS EC2 Instance
                    Docker Compose
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
           Next.js                 FastAPI
           Frontend                Backend
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                         ▼                         ▼
                    PostgreSQL                  AWS S3
                         ▲
                         │
                      Worker
                         │
                   ┌─────┴─────┐
                   ▼           ▼
                Gnani        Gemini
                 ASR         Summary
```

The EC2 instance runs:

- Caddy
- Next.js
- FastAPI
- background worker
- PostgreSQL

External services:

- AWS S3
- Gnani ASR
- Gemini

Only Caddy exposes public application ports.

```text
/api/*  → FastAPI
/*      → Next.js
```

---

## Upload Flow

Audio is uploaded directly from the browser to AWS S3.

```text
Browser
   │
   │ create upload
   ▼
FastAPI
   │
   │ create S3 multipart upload
   │ generate presigned URLs
   ▼
AWS S3

Browser ───────── direct multipart PUT ─────────► AWS S3
```

Flow:

1. The user selects an audio file.
2. Next.js asks FastAPI to initialize an upload.
3. FastAPI creates an AWS S3 multipart upload.
4. FastAPI generates short-lived presigned part URLs.
5. The browser uploads the audio parts directly to private AWS S3.
6. The browser sends uploaded part information back to FastAPI.
7. FastAPI validates and completes the multipart upload.
8. A durable processing job is stored in PostgreSQL.
9. The worker claims the job and begins processing.

Large audio bodies therefore do not pass through Next.js, Caddy, or FastAPI.

---

## Processing Pipeline

```text
AWS S3
   │
   ▼
Background Worker
   │
   ▼
Audio Processing
   │
   ▼
Gnani ASR
   │
   ▼
Transcript
   │
   ▼
Gemini
   │
   ▼
Structured Summary
   │
   ▼
PostgreSQL
   │
   ▼
FastAPI
   │
   ▼
Next.js UI
```

The background worker runs separately from the FastAPI web process.

Processing state is persisted in PostgreSQL, allowing work to continue independently from the browser session.

---

## Technology Stack

### Frontend

- Next.js
- React
- TypeScript

### Backend

- FastAPI
- Python
- SQLAlchemy
- Alembic

### Database

- PostgreSQL

### Storage

- AWS S3
- boto3

### AI Services

- Gnani ASR
- Google Gemini

### Infrastructure

- AWS EC2
- Docker
- Docker Compose
- Caddy
- HTTPS / automatic TLS

---

## Engineering Decisions

### Direct S3 multipart upload

Audio recordings can be much larger than normal API requests. Direct browser-to-S3 uploads keep large file transfers away from the application server while retaining a private bucket through presigned URLs.

### Separate background worker

Speech-to-text and summarization can take much longer than normal HTTP requests. A dedicated worker keeps long-running AI processing outside FastAPI's request path.

### PostgreSQL-backed processing state

PostgreSQL already stores application data, so durable job state can be maintained without introducing another queue service for the current project scale.

### Private S3

Audio objects are never made public. Temporary presigned URLs grant only short-lived upload or playback access.

### Docker Compose

The current application fits on one EC2 host. Docker Compose provides clear service isolation without unnecessary orchestration complexity.

### Caddy

Caddy provides HTTPS, automatic certificate management, HTTP-to-HTTPS redirects, and reverse proxy routing with very little configuration.

---

## Security

The production system uses:

- HTTPS through Caddy
- private AWS S3
- short-lived presigned S3 URLs
- EC2 IAM role for AWS access
- boto3's standard credential chain
- secrets through environment variables
- internal Docker networking
- PostgreSQL not publicly exposed
- FastAPI not directly exposed
- frontend container not directly exposed

Secrets, AWS credentials, database passwords, session keys, and provider API keys must never be committed to Git.

---

## Local Development

The local application also uses real AWS S3.

MinIO is not required.

Create the environment configuration from:

```powershell
Copy-Item .env.example .env
```

Add the required values locally.

Never commit `.env`.

Run the application using the repository's Docker Compose development configuration.

Typical startup:

```powershell
docker compose up -d --build
```

If the project uses the AWS profile Compose override:

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.aws-profile.yml `
  up -d --build
```

Local AWS access uses the normal AWS credential chain.

---

## Environment Configuration

Important environment variable names include:

```text
APP_ENV
APP_ORIGIN

POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
DATABASE_URL

SESSION_SECRET

AWS_REGION
S3_BUCKET

GNANI_API_KEY

GEMINI_API_KEY
GEMINI_MODEL

DOMAIN
```

Only variable names belong in documentation.

Real values must remain in ignored environment files.

---

## Production Deployment

Production:

https://notes.cipherxcel.app

The production Docker Compose stack runs on a single AWS EC2 instance.

Caddy is the only public application service and exposes ports:

```text
80
443
```

Routing:

```text
/api/* → backend:8000
/*     → frontend:3000
```

PostgreSQL uses a persistent Docker volume.

AWS S3, Gnani, and Gemini remain external services.

See [`DEPLOY_EC2.md`](DEPLOY_EC2.md) for detailed deployment instructions.

---

## Source Control and Deployment

GitHub is the source repository:

https://github.com/CipherXcel/GNANI_AI_PROJECT

Current deployment updates are manual:

```text
Local Development
       │
       │ git push
       ▼
     GitHub
       │
       │ git pull
       ▼
     AWS EC2
       │
       ▼
 Docker Compose
```

The current project does not claim automatic CI/CD.

---

## Testing

Frontend:

```powershell
cd frontend

npm run typecheck
npm run lint
npm run build
```

Backend tests should be run using the project's existing Python environment/test configuration.

---

## Repository Structure

```text
GNANI_AI_PROJECT/
│
├── backend/
│   ├── app/
│   └── tests/
│
├── frontend/
│   ├── app/
│   ├── components/
│   └── tests/
│
├── scripts/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Caddyfile
├── DEPLOY_EC2.md
├── .env.example
└── README.md
```

Important files:

| File | Purpose |
|---|---|
| `backend/app/api.py` | FastAPI routes and upload coordination |
| `backend/app/worker.py` | Background processing |
| `backend/app/storage.py` | AWS S3 client and presigned URLs |
| `frontend/app/architecture/page.tsx` | Production architecture explanation |
| `docker-compose.prod.yml` | Production Docker topology |
| `Caddyfile` | HTTPS and reverse proxy routing |
| `DEPLOY_EC2.md` | EC2 deployment instructions |

---

## Trade-offs and Future Improvements

The current architecture intentionally prioritizes simplicity.

Current limitations:

- one EC2 host is a single point of failure;
- PostgreSQL runs on the same host;
- persistent Docker storage is not an off-site backup;
- external AI providers affect processing availability.

Possible future improvements:

- managed PostgreSQL;
- automated off-site backups;
- independent worker scaling;
- stronger observability;
- automated CI/CD;
- multi-instance deployment.

These are future improvements and are not part of the current production architecture.

---

## Links

**Live Application**  
https://notes.cipherxcel.app

**Architecture**  
https://notes.cipherxcel.app/architecture

**GitHub Repository**  
https://github.com/CipherXcel/GNANI_AI_PROJECT