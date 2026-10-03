import math
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import PurePath
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.exc import SQLAlchemyError
from botocore.exceptions import BotoCoreError, ClientError
from .auth import owner
from .config import settings
from .database import get_db, now
from .models import Job, Note, Segment, WorkerHeartbeat, new_id
from .storage import client, presign

LANGUAGES = {"en-IN": "English", "hi-IN": "Hindi", "bn-IN": "Bengali", "gu-IN": "Gujarati",
             "kn-IN": "Kannada", "ml-IN": "Malayalam", "mr-IN": "Marathi", "pa-IN": "Punjabi",
             "ta-IN": "Tamil", "te-IN": "Telugu"}
EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".webm", ".opus", ".mp4", ".aiff"}


@asynccontextmanager
async def lifespan(app):
    settings()  # Validate configuration; provisioning S3 belongs to the operator.
    yield


app = FastAPI(title="Suno Audio Notes API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(BotoCoreError)
@app.exception_handler(ClientError)
async def storage_error(request: Request, exc):
    return JSONResponse(status_code=503, content={"detail": "Audio storage is temporarily unavailable. Please try again."})


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc):
    return JSONResponse(status_code=503, content={"detail": "The recording database is temporarily unavailable. Please try again."})


@app.get("/health")
def health(db: DbSession = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/api/config")
def config(workspace=Depends(owner), db: DbSession = Depends(get_db)):
    cfg = settings()
    last_seen = db.scalar(select(func.max(WorkerHeartbeat.seen_at)))
    return {"languages": LANGUAGES, "max_upload_bytes": cfg.max_upload_bytes,
            "gnani_configured": bool(cfg.gnani_api_key), "gemini_configured": bool(cfg.gemini_api_key),
            "worker_online": bool(last_seen and last_seen > now() - timedelta(seconds=60)),
            "github_repo_url": cfg.github_repo_url}


def owned(db, note_id, workspace, lock=False):
    query = select(Note).where(Note.id == note_id, Note.owner == workspace)
    if lock:
        query = query.with_for_update()
    note = db.scalar(query)
    if note is None:
        raise HTTPException(404, "This recording was not found in your workspace.")
    return note


def serialize(note, detail=False, db=None):
    fields = ("id", "title", "filename", "language", "size", "status", "progress", "stage_message",
              "duration", "total_chunks", "completed_chunks", "error", "error_stage", "created_at", "updated_at")
    result = {name: getattr(note, name) for name in fields}
    result["has_summary"] = bool(note.summary)
    if detail:
        result.update(transcript=note.transcript, summary=note.summary)
        result["segments"] = [{"start": s.start, "end": s.end, "text": s.text, "position": s.position}
                              for s in db.scalars(select(Segment).where(Segment.note_id == note.id).order_by(Segment.position))]
    return result


@app.get("/api/notes")
def list_notes(q: str = "", status: str = "", offset: int = 0, limit: int = 50,
               workspace=Depends(owner), db: DbSession = Depends(get_db)):
    conditions = [Note.owner == workspace]
    if q.strip():
        conditions.append(Note.title.ilike("%" + q.strip().replace("%", "\\%").replace("_", "\\_") + "%"))
    if status:
        conditions.append(Note.status == status)
    query = select(Note).where(*conditions).order_by(Note.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100))
    stats = db.execute(select(Note.status, func.count(), func.coalesce(func.sum(Note.duration), 0))
                       .where(Note.owner == workspace).group_by(Note.status)).all()
    return {"notes": [serialize(n) for n in db.scalars(query)],
            "total": db.scalar(select(func.count()).select_from(Note).where(*conditions)),
            "stats": {"total": sum(s[1] for s in stats), "ready": sum(s[1] for s in stats if s[0] == "ready"),
                      "processing": sum(s[1] for s in stats if s[0] in ("queued", "preparing", "transcribing", "summarizing")),
                      "duration": sum(s[2] for s in stats)}}


class UploadInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    title: str = Field(default="", max_length=200)
    size: int = Field(gt=0)
    language: str = "en-IN"
    content_type: str = Field(default="application/octet-stream", max_length=100)


@app.post("/api/uploads", status_code=201)
def begin_upload(body: UploadInput, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    cfg = settings()
    if body.language not in LANGUAGES:
        raise HTTPException(422, "Please choose a supported transcription language.")
    if body.size > cfg.max_upload_bytes:
        raise HTTPException(413, "This file exceeds the configured upload limit.")
    extension = PurePath(body.filename).suffix.lower()
    if extension not in EXTENSIONS:
        raise HTTPException(415, "Choose an audio file: WAV, MP3, M4A, AAC, FLAC, OGG, WebM, Opus, MP4, or AIFF.")
    active = db.scalar(select(func.count()).select_from(Note).where(Note.owner == workspace, Note.status.in_(
        ["uploading", "queued", "preparing", "transcribing", "summarizing"])))
    if active >= 10:
        raise HTTPException(429, "You have 10 active recordings. Wait for one to finish or remove an unfinished upload.")
    note_id = new_id()
    key = f"{workspace}/{note_id}/original{extension}"
    upload = client().create_multipart_upload(Bucket=cfg.s3_bucket, Key=key, ContentType=body.content_type)
    # Keep below S3's 10,000-part ceiling, with a bounded 16 MiB minimum.
    part_size = max(16 * 1024**2, math.ceil(body.size / 9999 / 1024**2) * 1024**2)
    note = Note(id=note_id, owner=workspace, title=body.title.strip() or PurePath(body.filename).stem[:200],
                filename=body.filename, language=body.language, size=body.size, content_type=body.content_type,
                object_key=key, upload_id=upload["UploadId"], part_size=part_size)
    db.add(note)
    try:
        db.commit()
    except Exception:
        client().abort_multipart_upload(Bucket=cfg.s3_bucket, Key=key, UploadId=upload["UploadId"])
        raise
    return {"id": note.id, "part_size": part_size, "part_count": math.ceil(note.size / part_size)}


@app.get("/api/uploads/{note_id}/parts/{number}")
def upload_part(note_id: str, number: int, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    note = owned(db, note_id, workspace)
    if note.status != "uploading" or not note.upload_id:
        raise HTTPException(409, "This upload is no longer active.")
    if not 1 <= number <= math.ceil(note.size / note.part_size):
        raise HTTPException(422, "Invalid upload part.")
    return {"url": presign("upload_part", {"Key": note.object_key, "UploadId": note.upload_id, "PartNumber": number})}


@app.post("/api/uploads/{note_id}/complete", status_code=202)
def complete_upload(note_id: str, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    note = owned(db, note_id, workspace, lock=True)
    if note.status != "uploading":
        return serialize(note)
    s3, bucket = client(), settings().s3_bucket
    # Listing from storage avoids trusting browser-provided ETags and sizes.
    parts = []
    try:
        for page in s3.get_paginator("list_parts").paginate(Bucket=bucket, Key=note.object_key, UploadId=note.upload_id):
            parts.extend(page.get("Parts", []))
        expected = math.ceil(note.size / note.part_size)
        if len(parts) != expected or sum(p["Size"] for p in parts) != note.size or [p["PartNumber"] for p in parts] != list(range(1, expected + 1)):
            raise HTTPException(409, "Some audio data is missing. Please retry the upload.")
        s3.complete_multipart_upload(Bucket=bucket, Key=note.object_key, UploadId=note.upload_id,
                                     MultipartUpload={"Parts": [{"ETag": p["ETag"], "PartNumber": p["PartNumber"]} for p in parts]})
    except ClientError as exc:
        # If S3 completion succeeded but the DB commit failed, finalization is safely repeatable.
        if exc.response["Error"]["Code"] != "NoSuchUpload":
            raise
        head = s3.head_object(Bucket=bucket, Key=note.object_key)
        if head["ContentLength"] != note.size:
            raise HTTPException(409, "Stored audio size did not match the upload.")
    note.upload_id = None
    note.status, note.progress, note.stage_message = "queued", 5, "Upload saved. Waiting for an available worker."
    db.add(Job(note_id=note.id))
    db.commit()
    return serialize(note)


@app.get("/api/notes/{note_id}")
def get_note(note_id: str, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    return serialize(owned(db, note_id, workspace), True, db)


@app.get("/api/notes/{note_id}/audio")
def get_audio(note_id: str, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    note = owned(db, note_id, workspace)
    if note.status == "uploading":
        raise HTTPException(409, "The audio is still uploading.")
    return {"url": presign("get_object", {"Key": note.object_key}, 3600)}


class RenameInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@app.patch("/api/notes/{note_id}")
def rename(note_id: str, body: RenameInput, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    note = owned(db, note_id, workspace)
    if not body.title.strip():
        raise HTTPException(422, "A recording title cannot be empty.")
    note.title = body.title.strip()
    db.commit()
    return serialize(note)


@app.post("/api/notes/{note_id}/retry", status_code=202)
def retry(note_id: str, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    note = owned(db, note_id, workspace, lock=True)
    if note.status != "failed":
        raise HTTPException(409, "Only a failed recording can be retried.")
    job = db.scalar(select(Job).where(Job.note_id == note.id))
    if not job:
        raise HTTPException(409, "This upload was not completed. Please upload the file again.")
    job.status, job.locked_by, job.lease_until = "queued", None, None
    note.status, note.error, note.error_stage, note.stage_message = "queued", None, None, "Queued to resume from saved progress."
    db.commit()
    return serialize(note)


@app.delete("/api/notes/{note_id}", status_code=204)
def delete_note(note_id: str, workspace=Depends(owner), db: DbSession = Depends(get_db)):
    note = owned(db, note_id, workspace, lock=True)
    if note.status in ("queued", "preparing", "transcribing", "summarizing"):
        raise HTTPException(409, "Wait for processing to finish before deleting this recording.")
    s3, bucket = client(), settings().s3_bucket
    if note.upload_id:
        try:
            s3.abort_multipart_upload(Bucket=bucket, Key=note.object_key, UploadId=note.upload_id)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchUpload":
                raise
    s3.delete_object(Bucket=bucket, Key=note.object_key)
    db.delete(note)
    db.commit()
