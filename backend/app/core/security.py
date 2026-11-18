import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, HTTPException, Request, Response
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.db.models import Audit, Membership, Project, Session, User, now
from app.db.session import session

DB = Annotated[DBSession, Depends(session)]
passwords = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = passwords.hash("timing-equalization-value")
COOKIE = "analyst_session"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_password(hashed: str, password: str) -> bool:
    try:
        return passwords.verify(hashed, password)
    except VerificationError:
        return False


def set_session(db: DBSession, output: Response, user: User):
    token = secrets.token_urlsafe(32)
    hours = settings().session_hours
    db.add(Session(user_id=user.id, token_hash=digest(token), expires_at=now() + timedelta(hours=hours)))
    output.set_cookie(
        COOKIE,
        token,
        max_age=hours * 3600,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="lax",
        path="/",
    )


def current_user(request: Request, db: DB) -> User:
    cookie = request.cookies.get(COOKIE, "")
    if not cookie or len(cookie) > 64:
        raise HTTPException(401, "Sign in to continue.")
    user = db.scalar(
        select(User)
        .join(Session, Session.user_id == User.id)
        .where(
            Session.token_hash == digest(cookie),
            Session.expires_at > now(),
        )
    )
    if not user:
        raise HTTPException(401, "Your session has expired.")
    return user


Actor = Annotated[User, Depends(current_user)]


def membership(db: DBSession, user: User, workspace_id: str, write=False, owner=False) -> Membership:
    member = db.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id,
            Membership.user_id == user.id,
        )
    )
    if not member:
        raise HTTPException(404, "Workspace not found.")
    if (write and member.role == "viewer") or (owner and member.role != "owner"):
        raise HTTPException(403, "Your workspace role does not allow this action.")
    return member


def project_for(db: DBSession, user: User, project_id: str, write=False) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found.")
    membership(db, user, project.workspace_id, write)
    return project


def audit(db: DBSession, user: User, workspace_id: str, action: str, subject: str):
    db.add(Audit(user_id=user.id, workspace_id=workspace_id, action=action, subject=subject))


def limiter(key: str, limit: int, seconds: int):
    url = settings().redis_url
    if not url:
        return
    try:
        with Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2) as client:
            script = """
                local n = redis.call('INCR', KEYS[1])
                if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
                return n
            """
            if client.eval(script, 1, f"limit:{key}", seconds) > limit:
                raise HTTPException(
                    429, "Rate limit exceeded. Try again shortly.", {"Retry-After": str(seconds)}
                )
    except RedisError as exc:
        raise HTTPException(503, "Rate limiter is unavailable.") from exc
