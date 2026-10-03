import logging
import signal
import tempfile
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path
from sqlalchemy import and_, or_, select, update
from .audio import chunk_plan, extract_chunk, probe, remove_overlap
from .config import settings
from .database import Session, now
from .models import Job, Note, Segment, WorkerHeartbeat
from .providers import ProcessingError, summarize, transcribe
from .storage import client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")
WORKER_ID = str(uuid.uuid4())
STOP = threading.Event()


class LeaseLost(Exception):
    pass


def claim_job():
    with Session.begin() as db:
        job = db.scalar(select(Job).where(or_(Job.status == "queued", and_(Job.status == "running", Job.lease_until < now())))
                        .order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        job.status, job.locked_by = "running", WORKER_ID
        job.lease_until = now() + timedelta(seconds=settings().lease_seconds)
        job.attempts += 1
        return job.id, job.note_id


def locked_job(db, job_id):
    job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if not job or job.locked_by != WORKER_ID or job.status != "running" or job.lease_until < now():
        raise LeaseLost()
    return job


def checkpoint(job_id, note_id, **values):
    with Session.begin() as db:
        locked_job(db, job_id)
        note = db.get(Note, note_id)
        if not note:
            raise LeaseLost()
        for key, value in values.items():
            setattr(note, key, value)


def heartbeat_loop(active, guard):
    while not STOP.is_set():
        try:
            with Session.begin() as db:
                heartbeat = db.get(WorkerHeartbeat, WORKER_ID)
                if heartbeat:
                    heartbeat.seen_at = now()
                else:
                    db.add(WorkerHeartbeat(id=WORKER_ID))
                with guard:
                    job_id = active[0]
                if job_id:
                    db.execute(update(Job).where(Job.id == job_id, Job.locked_by == WORKER_ID, Job.status == "running")
                               .values(lease_until=now() + timedelta(seconds=settings().lease_seconds)))
        except Exception:
            log.warning("Worker heartbeat could not be saved; will retry")
        STOP.wait(15)


def process(job_id, note_id):
    with Session() as db:
        note = db.get(Note, note_id)
        source_key, language, existing_transcript = note.object_key, note.language, note.transcript
    if not existing_transcript:
        checkpoint(job_id, note_id, status="preparing", progress=8, stage_message="Checking audio and preparing short sections", error=None)
        with tempfile.TemporaryDirectory(prefix="audionotes-") as tmp:
            source, chunk = Path(tmp) / "original", Path(tmp) / "chunk.wav"
            client().download_file(settings().s3_bucket, source_key, str(source))
            duration = probe(source)
            plan = list(chunk_plan(duration, settings().chunk_seconds, settings().chunk_overlap))
            checkpoint(job_id, note_id, duration=duration, total_chunks=len(plan), status="transcribing", progress=12)
            for i, (start, end) in enumerate(plan):
                with Session() as db:
                    existing = db.scalar(select(Segment).where(Segment.note_id == note_id, Segment.position == i))
                    prev = db.scalar(select(Segment).where(Segment.note_id == note_id, Segment.position == i - 1))
                if existing:
                    continue
                checkpoint(job_id, note_id, stage_message=f"Transcribing section {i + 1} of {len(plan)}")
                extract_chunk(source, chunk, start, end - start)
                transcript = transcribe(chunk, language)
                if prev:
                    transcript = remove_overlap(prev.text, transcript)
                with Session.begin() as db:
                    locked_job(db, job_id)
                    db.add(Segment(note_id=note_id, position=i, start=start, end=end, text=transcript))
                    current = db.get(Note, note_id)
                    current.completed_chunks = i + 1
                    current.progress = 12 + int(68 * (i + 1) / len(plan))
            with Session() as db:
                existing_transcript = "\n\n".join(s.text for s in db.scalars(select(Segment).where(Segment.note_id == note_id)
                                                      .order_by(Segment.position)) if s.text)
            if not existing_transcript.strip():
                raise ProcessingError("No speech was detected. Check that the recording contains clear speech and that the selected language is correct.")
            checkpoint(job_id, note_id, transcript=existing_transcript)
    checkpoint(job_id, note_id, status="summarizing", progress=85, stage_message="Creating your summary and key takeaways", error=None)
    summary = summarize(existing_transcript, lambda msg: checkpoint(job_id, note_id, stage_message=msg))
    with Session.begin() as db:
        job = locked_job(db, job_id)
        note = db.get(Note, note_id)
        note.summary, note.status, note.progress = summary, "ready", 100
        note.stage_message, note.error, note.error_stage = "Your notes are ready", None, None
        job.status, job.locked_by, job.lease_until = "done", None, None


def fail(job_id, note_id, message):
    with Session.begin() as db:
        job = locked_job(db, job_id)
        note = db.get(Note, note_id)
        note.error_stage, note.status, note.error = note.status, "failed", message
        note.stage_message = "Processing stopped. Saved progress is available."
        job.status, job.locked_by, job.lease_until = "failed", None, None


def main():
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    active, guard = [None], threading.Lock()
    thread = threading.Thread(target=heartbeat_loop, args=(active, guard), daemon=True)
    thread.start()
    log.info("Audio worker started")
    while not STOP.is_set():
        try:
            job = claim_job()
            if not job:
                STOP.wait(2)
                continue
            with guard:
                active[0] = job[0]
            try:
                process(*job)
                log.info("Recording %s completed", job[1])
            except LeaseLost:
                log.warning("Job lease lost; another worker owns the recording")
            except ProcessingError as exc:
                fail(*job, str(exc))
                log.warning("Recording %s stopped: %s", job[1], exc)
            except Exception as exc:
                # Log type only: provider requests may contain signed URLs or credentials.
                log.error("Recording %s failed (%s)", job[1], type(exc).__name__)
                fail(*job, "Processing was interrupted by a service or storage error. Your saved progress is safe; please retry.")
            finally:
                with guard:
                    active[0] = None
        except Exception as exc:
            log.error("Worker database unavailable (%s); retrying", type(exc).__name__)
            STOP.wait(5)
    thread.join(timeout=2)


if __name__ == "__main__":
    main()
