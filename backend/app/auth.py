import hashlib
import hmac
import uuid
from fastapi import HTTPException, Request, Response
from .config import settings

COOKIE = "audionotes_workspace"


def signature(value):
    return hmac.new(settings().session_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def owner(request: Request, response: Response):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != settings().app_origin:
            raise HTTPException(403, "This request came from an untrusted website.")
    raw = request.cookies.get(COOKIE, "")
    value, _, sig = raw.partition(".")
    try:
        uuid.UUID(value)
        valid = hmac.compare_digest(sig, signature(value))
    except ValueError:
        valid = False
    if not valid:
        value = str(uuid.uuid4())
        response.set_cookie(COOKIE, f"{value}.{signature(value)}", httponly=True,
                            secure=settings().cookie_secure, samesite="lax", max_age=365 * 86400, path="/")
    return value
