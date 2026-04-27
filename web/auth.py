"""
Authentication module.

Monthly codes: HMAC-SHA256(email + YYYY-MM + SECRET_KEY)[:8].upper()
Auto-rotate every month. No database needed for codes.
Subscribers managed via data/subscribers.json.

Sessions: signed JWT (HS256), 24h expiry.
"""
import hmac
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = "HS256"
SESSION_HOURS = 24
SUBSCRIBERS_FILE = Path(__file__).parent / "data" / "subscribers.json"


# ── Subscribers ───────────────────────────────────────────────────────────────

def _load_subscribers() -> list[str]:
    if not SUBSCRIBERS_FILE.exists():
        return []
    with open(SUBSCRIBERS_FILE) as f:
        data = json.load(f)
    return [e.lower() for e in data.get("subscribers", [])]


def _save_subscribers(emails: list[str]) -> None:
    SUBSCRIBERS_FILE.parent.mkdir(exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump({"subscribers": sorted(set(e.lower() for e in emails))}, f, indent=2)


def is_subscriber(email: str) -> bool:
    return email.lower() in _load_subscribers()


def add_subscriber(email: str) -> None:
    subs = _load_subscribers()
    subs.append(email.lower())
    _save_subscribers(subs)


def remove_subscriber(email: str) -> bool:
    subs = _load_subscribers()
    new = [s for s in subs if s != email.lower()]
    if len(new) == len(subs):
        return False
    _save_subscribers(new)
    return True


def list_subscribers() -> list[str]:
    return _load_subscribers()


# ── Monthly Code ──────────────────────────────────────────────────────────────

def generate_monthly_code(email: str) -> str:
    """
    Deterministic 8-char code. Changes every calendar month.
    Same code is generated every time for the same email+month+key — no storage needed.
    """
    now = datetime.now(timezone.utc)
    period = f"{now.year}-{now.month:02d}"
    message = f"{email.lower()}:{period}"
    digest = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()
    return digest[:8].upper()


def verify_code(email: str, submitted_code: str) -> bool:
    expected = generate_monthly_code(email)
    return hmac.compare_digest(submitted_code.upper().strip(), expected)


# ── JWT Session ───────────────────────────────────────────────────────────────

def create_session_token(email: str) -> str:
    payload = {
        "sub": email.lower(),
        "exp": datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> str | None:
    """Return email if valid, None otherwise."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
