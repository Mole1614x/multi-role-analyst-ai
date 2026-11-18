import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.observability import log
from app.core.security import (
    COOKIE,
    DB,
    DUMMY_HASH,
    Actor,
    digest,
    limiter,
    passwords,
    set_session,
    verify_password,
)
from app.db.models import Membership, ResetToken, Session, User, Workspace, now

router = APIRouter(prefix="/auth", tags=["authentication"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=200)


class Register(Credentials):
    name: str = Field(min_length=1, max_length=100, pattern=r"\S")


class EmailInput(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str = Field(min_length=40, max_length=64)
    password: str = Field(min_length=12, max_length=200)


def user_data(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "admin": user.id in settings().admin_user_ids,
    }


def throttle(request: Request, email: str, action: str):
    limiter(f"auth:{action}:{digest(email)}", 8, 300)
    limiter(f"auth:{action}:ip:{request.client.host if request.client else 'unknown'}", 45, 300)


@router.get("/config")
def configuration():
    config = settings()
    return {
        "password_reset": bool(config.smtp_host and config.smtp_from),
        "llm": config.llm_provider if config.llm_api_key else "none",
        "research": bool(config.research_api_key),
    }


@router.post("/register", status_code=201)
def register(body: Register, request: Request, response: Response, db: DB):
    email = body.email.casefold()
    throttle(request, email, "register")
    user = User(name=body.name.strip(), email=email, password_hash=passwords.hash(body.password))
    workspace = Workspace(name=f"{body.name.strip()[:85]}'s workspace")
    db.add_all([user, workspace])
    try:
        db.flush()
        db.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))
        set_session(db, response, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This email already has an account.") from exc
    return user_data(user)


@router.post("/login")
def login(body: Credentials, request: Request, response: Response, db: DB):
    email = body.email.casefold()
    throttle(request, email, "login")
    user = db.scalar(select(User).where(User.email == email))
    if not verify_password(user.password_hash if user else DUMMY_HASH, body.password) or not user:
        raise HTTPException(401, "The email or password is incorrect.")
    if passwords.check_needs_rehash(user.password_hash):
        user.password_hash = passwords.hash(body.password)
    set_session(db, response, user)
    db.commit()
    return user_data(user)


@router.get("/me")
def me(user: Actor):
    return user_data(user)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB):
    value = request.cookies.get(COOKIE)
    if value:
        db.execute(delete(Session).where(Session.token_hash == digest(value)))
        db.commit()
    response.delete_cookie(COOKIE, secure=settings().cookie_secure, httponly=True)


def send_reset(email: str, token: str):
    config = settings()
    message = EmailMessage()
    message["From"] = config.smtp_from
    message["To"] = email
    message["Subject"] = "Reset your Analyst Workspace password"
    url = f"{config.origin}/reset?{urlencode({'token': token})}"
    message.set_content(f"Open this link within 30 minutes to reset your password.\n\n{url}")
    try:
        import ssl

        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=8) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        log("password_reset_delivery_failed", error_type=type(exc).__name__)


@router.post("/forgot", status_code=202)
def forgot(body: EmailInput, request: Request, background: BackgroundTasks, db: DB):
    email = body.email.casefold()
    throttle(request, email, "forgot")
    config = settings()
    if not (config.smtp_host and config.smtp_from):
        raise HTTPException(503, "Password reset email is unavailable in this deployment.")
    user = db.scalar(select(User).where(User.email == email))
    if user:
        token = secrets.token_urlsafe(32)
        db.add(
            ResetToken(user_id=user.id, token_hash=digest(token), expires_at=now() + timedelta(minutes=30))
        )
        db.commit()
        background.add_task(send_reset, email, token)
    return {"message": "If an account exists, a password reset link will be sent."}


@router.post("/reset")
def reset(body: PasswordReset, request: Request, db: DB):
    limiter(f"auth:reset:{request.client.host if request.client else 'unknown'}", 15, 300)
    token_hash = digest(body.token)
    record = db.execute(
        delete(ResetToken)
        .where(ResetToken.token_hash == token_hash, ResetToken.expires_at > now())
        .returning(ResetToken.user_id)
    ).first()
    if not record:
        raise HTTPException(400, "The password reset link is invalid or expired.")
    user_id = record[0]
    db.execute(update(User).where(User.id == user_id).values(password_hash=passwords.hash(body.password)))
    db.execute(delete(ResetToken).where(ResetToken.user_id == user_id))
    db.execute(delete(Session).where(Session.user_id == user_id))
    db.commit()
    return {"message": "Password updated. Sign in with your new password."}
