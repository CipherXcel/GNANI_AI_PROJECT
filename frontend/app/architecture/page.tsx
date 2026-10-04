"use client";

import { useEffect, useState } from "react";
import {
  AudioLines,
  ExternalLink,
  FileText,
  Github,
  HardDrive,
  Server,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";

import { Shell } from "@/components/shell";
import { api, Config } from "@/lib/api";

const LIVE_URL = "https://notes.cipherxcel.app";

export default function Architecture() {
  const [repo, setRepo] = useState(
    "https://github.com/CipherXcel/GNANI_AI_PROJECT",
  );

  useEffect(() => {
    api<Config>("/config")
      .then((config) => {
        if (config.github_repo_url) {
          setRepo(config.github_repo_url);
        }
      })
      .catch(() => {
        // Keep the public repository fallback.
      });
  }, []);

  return (
    <Shell>
      <main className="architecture-page">
        <div className="eyebrow">PRODUCTION ARCHITECTURE</div>

        <h1>From sound to something useful.</h1>

        <p className="intro">
          Suno turns uploaded recordings into transcripts and structured notes.
          The application is deployed on AWS EC2, stores audio privately in AWS
          S3, transcribes with Gnani ASR, and generates structured summaries
          with Gemini.
        </p>

        <div className="repo-banner">
          <div>
            <strong>Live production system</strong>
            <p>
              Next.js, FastAPI, PostgreSQL, the background worker, and Caddy run
              through Docker Compose on one AWS EC2 instance.
            </p>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <a
              className="button secondary"
              href={LIVE_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink size={17} />
              Live application
            </a>

            <a
              className="button secondary"
              href={repo}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Github size={17} />
              GitHub
            </a>
          </div>
        </div>

        <p>
          <br />
        </p>

        <div
          className="architecture-flow"
          aria-label="Upload to storage, background transcription, and AI summary"
        >
          <div>
            <UploadCloud size={25} />
            <strong>Upload</strong>
            <span>Browser + Next.js</span>
          </div>

          <i className="flow-line" />

          <div>
            <HardDrive size={25} />
            <strong>Store</strong>
            <span>Private AWS S3</span>
          </div>

          <i className="flow-line" />

          <div>
            <AudioLines size={25} />
            <strong>Transcribe</strong>
            <span>Gnani ASR</span>
          </div>

          <i className="flow-line" />

          <div>
            <Sparkles size={25} />
            <strong>Summarize</strong>
            <span>Gemini</span>
          </div>

          <i className="flow-line" />

          <div>
            <FileText size={25} />
            <strong>Revisit</strong>
            <span>PostgreSQL history</span>
          </div>
        </div>

        <div className="architecture-grid">
          <section className="wide">
            <h2>Production architecture</h2>

            <p>
              The production application runs on one AWS EC2 instance using
              Docker Compose. The EC2 Docker network contains Caddy, the
              Next.js frontend, FastAPI, PostgreSQL, and the background worker.
              AWS S3, Gnani ASR, and Gemini remain external managed services.
            </p>

            <p>
              Caddy is the only public application entry point. Ports 80 and
              443 are exposed publicly. Requests under <code>/api/*</code> are
              routed to FastAPI on port 8000, while all other requests are
              routed to Next.js on port 3000.
            </p>

            <p>
              Caddy also manages HTTPS certificates and redirects HTTP traffic
              to HTTPS. PostgreSQL, FastAPI, the worker, and the Next.js
              container are not directly exposed to the internet.
            </p>
          </section>

          <section>
            <h2>1. Direct multipart upload</h2>

            <p>
              The Next.js frontend first asks FastAPI to create an upload.
              FastAPI creates a private object key and an AWS S3 multipart
              upload, then returns short-lived presigned URLs for the
              individual parts.
            </p>

            <p>
              The browser uploads the audio directly to private AWS S3. The
              audio file itself does not pass through Next.js, Caddy, or
              FastAPI.
            </p>

            <p>
              Up to three 16 MiB parts can upload concurrently. Failed parts
              use bounded retries. After upload, the browser sends part ETags
              back to FastAPI, which validates and completes the multipart
              upload.
            </p>
          </section>

          <section>
            <h2>2. Durable background processing</h2>

            <p>
              Completing an upload stores processing state in PostgreSQL. The
              HTTP request can return while a separate Python worker continues
              the long-running work.
            </p>

            <p>
              Workers claim jobs using <code>FOR UPDATE SKIP LOCKED</code>, so
              multiple workers can safely consume the queue if the deployment
              is scaled later.
            </p>

            <p>
              Worker leases, heartbeats, and persisted processing state allow
              interrupted work to be recovered instead of permanently
              remaining stuck.
            </p>
          </section>

          <section>
            <h2>3. Handling long audio</h2>

            <p>
              FFprobe first verifies that the uploaded object contains
              decodable audio. FFmpeg converts the source incrementally to
              mono, 16 kHz PCM WAV sections.
            </p>

            <p>
              Each transcription section is at most about 30 seconds long with
              a small overlap to reduce words lost at boundaries.
            </p>

            <p>
              Sections are sent sequentially to Gnani ASR. Completed transcript
              sections are checkpointed in PostgreSQL so retries can reuse work
              that has already finished.
            </p>
          </section>

          <section>
            <h2>4. Structured AI summaries</h2>

            <p>
              Gemini receives transcript text rather than the original audio.
              The summarization step produces a structured result containing
              an overview, key takeaways, topics, and explicitly stated action
              items.
            </p>

            <p>
              Long transcripts are summarized in bounded sections and combined
              into the final result.
            </p>

            <p>
              The transcript is persisted before summarization begins, so a
              Gemini failure does not require the audio to be transcribed again.
            </p>
          </section>

          <section>
            <h2>What lives where</h2>

            <p>
              <strong>PostgreSQL:</strong> recording metadata, processing
              states, transcripts, summary data, transcript checkpoints, and
              durable job state.
            </p>

            <p>
              <strong>AWS S3:</strong> original audio stored in a private
              bucket. Short-lived presigned URLs grant temporary upload and
              playback access.
            </p>

            <p>
              <strong>Browser:</strong> upload progress, playback controls, and
              a signed HttpOnly workspace cookie. Audio and transcripts are not
              stored in localStorage.
            </p>
          </section>

          <section>
            <h2>Visible progress and failures</h2>

            <p>
              Upload progress is based on bytes actually transferred. During
              processing, the frontend polls persisted state and shows queued,
              transcription, summarization, ready, or failed states.
            </p>

            <p>
              Provider timeouts, invalid audio, missing configuration, rate
              limits, and storage failures surface as visible error states.
              Provider calls use bounded retries where appropriate.
            </p>

            <p>
              A failed recording can retain already completed transcript work
              so retrying does not necessarily repeat the full pipeline.
            </p>
          </section>

          <section className="wide">
            <h2>
              <Server
                size={19}
                style={{ verticalAlign: "text-bottom", marginRight: 7 }}
              />
              Deployment flow
            </h2>

            <p>
              GitHub is the source repository. Production updates are currently
              manual rather than automatic.
            </p>

            <p>
              <strong>Local development → GitHub → AWS EC2 → Docker Compose</strong>
            </p>

            <p>
              Changes are tested locally, committed and pushed to GitHub, then
              pulled onto the EC2 host before the affected Docker images are
              rebuilt and containers recreated.
            </p>

            <p>
              The project does not currently claim an automatic GitHub Actions
              deployment pipeline.
            </p>
          </section>

          <section className="wide">
            <h2>
              <ShieldCheck
                size={19}
                style={{ verticalAlign: "text-bottom", marginRight: 7 }}
              />
              Security boundaries
            </h2>

            <p>
              Production traffic uses HTTPS through Caddy. PostgreSQL is not
              publicly exposed, and application services communicate through
              the internal Docker network.
            </p>

            <p>
              AWS S3 remains private. Browser access uses short-lived presigned
              URLs, while EC2 receives AWS permissions through its IAM role and
              boto3&apos;s standard credential chain instead of permanent AWS
              access keys stored in application code.
            </p>

            <p>
              Gnani, Gemini, database, and session secrets are supplied through
              environment configuration and are not sent to the browser.
            </p>
          </section>

        </div>

        <div className="repo-banner">
          <div>
            <strong>Explore the implementation</strong>
            <p>
              View the frontend, FastAPI backend, AWS S3 integration,
              PostgreSQL-backed worker pipeline, Docker configuration, and
              deployment setup in the repository.
            </p>
          </div>

          <a
            className="button secondary"
            href={repo}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Github size={17} />
            View repository on GitHub
          </a>
        </div>
      </main>
    </Shell>
  );
}