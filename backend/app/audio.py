import json
import math
import re
import subprocess
from .providers import ProcessingError


def probe(path):
    try:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                                capture_output=True, text=True, timeout=120, check=True)
        data = json.loads(result.stdout)
        if not any(s.get("codec_type") == "audio" for s in data.get("streams", [])):
            raise ValueError("no audio stream")
        duration = float(data["format"]["duration"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid duration")
        return duration
    except (subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise ProcessingError("This file could not be read as audio. It may be corrupt or empty. Export it as WAV or MP3 and upload it again.") from exc


def chunk_plan(duration, seconds=30, overlap=1):
    if seconds <= overlap or overlap < 0:
        raise ValueError("Invalid chunk configuration")
    start = 0.0
    while start < duration:
        end = min(start + seconds, duration)
        yield start, end
        if end == duration:
            break
        start += seconds - overlap


def extract_chunk(source, destination, start, duration):
    try:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(start), "-i", str(source),
                        "-t", str(duration), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination)],
                       capture_output=True, timeout=180, check=True)
    except subprocess.SubprocessError as exc:
        raise ProcessingError("A section of the audio could not be decoded. The file may be damaged; try exporting it as WAV or MP3.") from exc


def remove_overlap(previous, current):
    """Remove exact repeated word runs introduced by the 1-second audio overlap."""
    left, right = previous.split(), current.split()
    clean = lambda value: re.sub(r"[^\w]", "", value).casefold()
    for size in range(min(18, len(left), len(right)), 1, -1):
        if [clean(w) for w in left[-size:]] == [clean(w) for w in right[:size]]:
            return " ".join(right[size:])
    return current
