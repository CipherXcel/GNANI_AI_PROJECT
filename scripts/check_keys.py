"""Small provider checks. Never prints credentials or request URLs containing keys."""
import json
import pathlib
import urllib.request
import urllib.error

env = dict(line.split("=", 1) for line in (pathlib.Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8-sig").splitlines() if "=" in line)
request = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": env["GEMINI_API_KEY"]})
try:
    response = urllib.request.urlopen(request, timeout=30)
    data = json.load(response)
    print(json.dumps({"gemini_status": response.status, "models": [m["name"] for m in data.get("models", []) if "flash" in m["name"]][:12]}))
except urllib.error.HTTPError as error:
    data = json.load(error)
    print(json.dumps({"gemini_status": error.code, "message": "Provider rejected the credentials or request"}))
