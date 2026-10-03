from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
import json
import subprocess
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.api import app
from app.audio import chunk_plan, probe, remove_overlap
from app.auth import COOKIE
from app.config import settings
from app.database import Session, now
from app.models import Job, Note, Segment
from app.providers import ProcessingError, request_with_retry, split_text
from app import worker
from app.storage import client

SUMMARY = {"overview": "A test recording about a project.", "key_points": ["Build an audio notes app."], "action_items": [], "topics": ["Audio"]}


@pytest.fixture
def api():
    with TestClient(app) as value:
        value.get("/api/config")
        yield value


def upload(api, content=b"fake audio", filename="example.wav"):
    response = api.post("/api/uploads", json={"filename": filename, "size": len(content), "language": "en-IN"})
    assert response.status_code == 201, response.text
    note_id = response.json()["id"]
    with Session() as db:
        note = db.get(Note, note_id)
        client().upload_part(Bucket=settings().s3_bucket, Key=note.object_key, UploadId=note.upload_id, PartNumber=1, Body=content)
    return note_id


def test_chunk_plan_long_and_boundaries():
    for seconds in (.1, 30, 31, 60, 121, 7200):
        plan = list(chunk_plan(seconds))
        assert plan[0][0] == 0 and plan[-1][1] == seconds
        assert all(0 < end - start <= 30 for start, end in plan)
        assert all(plan[i][0] == plan[i-1][1]-1 for i in range(1, len(plan)))
    assert remove_overlap("We will test the project", "the project tomorrow morning") == "tomorrow morning"
    assert remove_overlap("One thought", "Another thought") == "Another thought"


def test_llm_chunking_does_not_truncate():
    text = ("A long recording has useful ideas. " * 3000).strip()
    pieces = list(split_text(text))
    assert len(pieces) > 1 and max(map(len, pieces)) <= 18000
    assert " ".join(pieces) == text


def test_workspace_isolation_and_csrf(api):
    note_id = upload(api)
    with TestClient(app) as other:
        assert other.get(f"/api/notes/{note_id}").status_code == 404
        assert other.delete(f"/api/notes/{note_id}").status_code == 404
        assert other.get("/api/notes").json()["total"] == 0
    assert api.patch(f"/api/notes/{note_id}", json={"title":"changed"}, headers={"Origin":"https://untrusted.invalid"}).status_code == 403
    assert api.get(f"/api/notes/{note_id}").status_code == 200
    assert api.delete(f"/api/notes/{note_id}").status_code == 204


def test_multipart_validation_and_atomic_finalize(api):
    assert api.post("/api/uploads",json={"filename":"virus.exe","size":12}).status_code == 415
    assert api.post("/api/uploads",json={"filename":"empty.wav","size":0}).status_code == 422
    assert api.post("/api/uploads",json={"filename":"big.wav","size":settings().max_upload_bytes+1}).status_code == 413
    note_id = api.post("/api/uploads",json={"filename":"audio.wav","size":5}).json()["id"]
    assert api.post(f"/api/uploads/{note_id}/complete").status_code == 409
    api.delete(f"/api/notes/{note_id}")
    note_id = upload(api)
    assert api.get(f"/api/uploads/{note_id}/parts/2").status_code == 422
    assert api.post(f"/api/uploads/{note_id}/complete").status_code == 202
    assert api.post(f"/api/uploads/{note_id}/complete").status_code == 202
    with Session() as db:
        assert len(list(db.scalars(select(Job).where(Job.note_id == note_id)))) == 1
        assert db.get(Note, note_id).status == "queued"
    assert api.delete(f"/api/notes/{note_id}").status_code == 409


def test_summary_retry_preserves_transcript_and_does_not_retranscribe(api, monkeypatch, tmp_path):
    source = tmp_path / "speech.wav"
    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","sine=frequency=300:duration=65","-ac","1","-ar","16000",str(source)],check=True)
    note_id = upload(api, source.read_bytes())
    api.post(f"/api/uploads/{note_id}/complete")
    calls = []
    def fake_asr(path, language):
        calls.append(path)
        assert probe(path) <= 30.01
        return f"Section {len(calls)} discusses building and testing audio notes."
    monkeypatch.setattr(worker,"transcribe",fake_asr)
    monkeypatch.setattr(worker,"summarize",lambda *args: (_ for _ in ()).throw(ProcessingError("Summary service unavailable")))
    job = worker.claim_job()
    with pytest.raises(ProcessingError):
        worker.process(*job)
    worker.fail(*job,"Summary service unavailable")
    saved = api.get(f"/api/notes/{note_id}").json()
    assert saved["status"] == "failed" and saved["error_stage"] == "summarizing"
    assert saved["transcript"] and len(saved["segments"]) == 3
    assert api.post(f"/api/notes/{note_id}/retry").status_code == 202
    monkeypatch.setattr(worker,"summarize",lambda *args: SUMMARY)
    worker.process(*worker.claim_job())
    ready = api.get(f"/api/notes/{note_id}").json()
    assert ready["status"] == "ready" and ready["progress"] == 100
    assert ready["summary"] == SUMMARY and len(calls) == 3
    assert api.delete(f"/api/notes/{note_id}").status_code == 204


def test_corrupt_audio_fails_visibly(api):
    note_id=upload(api,b"not an audio file")
    api.post(f"/api/uploads/{note_id}/complete")
    job=worker.claim_job()
    with pytest.raises(ProcessingError,match="corrupt") as exc:
        worker.process(*job)
    worker.fail(*job,str(exc.value))
    note=api.get(f"/api/notes/{note_id}").json()
    assert note["status"]=="failed" and "corrupt" in note["error"]
    api.delete(f"/api/notes/{note_id}")


def test_concurrent_claim_and_stale_lease_recovery(api):
    note_id=upload(api)
    api.post(f"/api/uploads/{note_id}/complete")
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=list(pool.map(lambda _:worker.claim_job(),range(2)))
    assert sum(j is not None for j in jobs)==1
    active=next(j for j in jobs if j)
    with Session.begin() as db:
        job=db.get(Job,active[0]);job.lease_until=now()-timedelta(seconds=1);job.locked_by="dead-worker"
    with pytest.raises(worker.LeaseLost):
        worker.checkpoint(*active,status="ready")
    reclaimed=worker.claim_job()
    assert reclaimed==active
    with Session() as db:
        assert db.get(Job,active[0]).attempts==2


def test_provider_retry_and_safe_errors(monkeypatch):
    monkeypatch.setattr("app.providers.time.sleep",lambda _:None)
    responses=iter([httpx.Response(429),httpx.Response(503),httpx.Response(200,json={"ok":True})])
    assert request_with_retry(lambda:next(responses),"Test provider")=={"ok":True}
    with pytest.raises(ProcessingError,match="API key"):
        request_with_retry(lambda:httpx.Response(403),"Test provider")
    with pytest.raises(ProcessingError,match="quota"):
        request_with_retry(lambda:httpx.Response(429),"Test provider")


def test_worker_restart_skips_completed_chunks(api, monkeypatch, tmp_path):
    source = tmp_path / "restart.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=65",
                    "-ac", "1", "-ar", "16000", str(source)], check=True)
    note_id = upload(api, source.read_bytes())
    api.post(f"/api/uploads/{note_id}/complete")
    calls = []
    def interrupted(path, language):
        calls.append("attempt")
        if len(calls) == 2:
            raise RuntimeError("simulated process interruption")
        return "The first section was saved before the interruption."
    monkeypatch.setattr(worker, "transcribe", interrupted)
    job = worker.claim_job()
    with pytest.raises(RuntimeError):
        worker.process(*job)
    with Session.begin() as db:
        active = db.get(Job, job[0])
        active.lease_until = now() - timedelta(seconds=1)
        active.locked_by = "previous-process"
        assert db.get(Note, note_id).completed_chunks == 1
    resumed = []
    monkeypatch.setattr(worker, "transcribe", lambda *args: resumed.append(1) or "Another section of the recording.")
    monkeypatch.setattr(worker, "summarize", lambda *args: SUMMARY)
    worker.process(*worker.claim_job())
    ready = api.get(f"/api/notes/{note_id}").json()
    assert len(resumed) == 2
    assert len(ready["segments"]) == 3 and ready["status"] == "ready"
