from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.analytics.roles import ROLES, definitions
from app.core.config import settings
from app.core.security import DB, Actor, audit, membership, project_for
from app.db.models import Audit, Dataset, Job, Membership, Project, User, Workspace

router = APIRouter(tags=["workspaces"])


class ProjectInput(BaseModel):
    name: str = Field(min_length=2, max_length=100, pattern=r"\S")
    description: str = Field(default="", max_length=2000)
    roles: list[str] = Field(min_length=1, max_length=12)


class ProjectCreate(ProjectInput):
    workspace_id: str = Field(max_length=36)


class MemberInput(BaseModel):
    user_id: str = Field(min_length=36, max_length=36)
    role: Literal["editor", "viewer"]


def data(row: Project) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "roles": row.roles,
        "workspace_id": row.workspace_id,
        "created_at": row.created_at.isoformat() + "Z",
    }


def validate_roles(roles: list[str]) -> list[str]:
    if len(set(roles)) != len(roles) or not set(roles) <= ROLES.keys():
        raise HTTPException(422, "Choose distinct supported analyst roles.")
    return roles


@router.get("/roles")
def roles():
    return definitions()


@router.get("/workspaces")
def workspaces(db: DB, user: Actor):
    rows = db.execute(
        select(Workspace, Membership)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id)
        .order_by(Workspace.created_at)
    )
    return [{"id": workspace.id, "name": workspace.name, "role": member.role} for workspace, member in rows]


@router.get("/projects")
def projects(db: DB, user: Actor):
    rows = db.scalars(
        select(Project)
        .join(Membership, Membership.workspace_id == Project.workspace_id)
        .where(Membership.user_id == user.id)
        .order_by(Project.created_at.desc())
    )
    return [data(row) for row in rows]


@router.post("/projects", status_code=201)
def create(body: ProjectCreate, db: DB, user: Actor):
    membership(db, user, body.workspace_id, write=True)
    project = Project(
        workspace_id=body.workspace_id,
        name=body.name.strip(),
        description=body.description,
        roles=validate_roles(body.roles),
    )
    db.add(project)
    db.flush()
    audit(db, user, project.workspace_id, "project.created", project.id)
    db.commit()
    return data(project)


@router.get("/projects/{project_id}")
def project(project_id: str, db: DB, user: Actor):
    row = project_for(db, user, project_id)
    return data(row) | {"access": membership(db, user, row.workspace_id).role}


@router.patch("/projects/{project_id}")
def change(project_id: str, body: ProjectInput, db: DB, user: Actor):
    row = project_for(db, user, project_id, write=True)
    row.name, row.description, row.roles = body.name.strip(), body.description, validate_roles(body.roles)
    audit(db, user, row.workspace_id, "project.updated", row.id)
    db.commit()
    return data(row)


@router.get("/workspaces/{workspace_id}/members")
def members(workspace_id: str, db: DB, user: Actor):
    membership(db, user, workspace_id)
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.workspace_id == workspace_id)
        .order_by(Membership.created_at)
    )
    return [{"id": actor.id, "name": actor.name, "role": member.role} for member, actor in rows]


@router.put("/workspaces/{workspace_id}/members")
def set_member(workspace_id: str, body: MemberInput, db: DB, user: Actor):
    membership(db, user, workspace_id, owner=True)
    actor = db.get(User, body.user_id)
    if actor is None:
        raise HTTPException(404, "Account ID not found.")
    member = db.scalar(
        select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == actor.id)
    )
    if member and member.role == "owner":
        raise HTTPException(409, "The workspace owner must retain owner access.")
    if member:
        member.role = body.role
    else:
        db.add(Membership(workspace_id=workspace_id, user_id=actor.id, role=body.role))
    audit(db, user, workspace_id, "membership.updated", actor.id)
    try:
        db.commit()
    except IntegrityError as exc:
        raise HTTPException(409, "Workspace membership changed concurrently. Try again.") from exc
    return {"id": actor.id, "name": actor.name, "role": body.role}


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=204)
def remove_member(workspace_id: str, user_id: str, db: DB, user: Actor):
    membership(db, user, workspace_id, owner=True)
    member = membership(db, User(id=user_id), workspace_id)
    if member.role == "owner":
        raise HTTPException(409, "The workspace owner must retain owner access.")
    db.delete(member)
    audit(db, user, workspace_id, "membership.removed", user_id)
    db.commit()


@router.get("/workspaces/{workspace_id}/activity")
def activity(workspace_id: str, db: DB, user: Actor):
    membership(db, user, workspace_id, owner=True)
    entries = db.scalars(
        select(Audit).where(Audit.workspace_id == workspace_id).order_by(Audit.created_at.desc()).limit(100)
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "actor": row.user_id,
            "subject": row.subject,
            "created_at": row.created_at.isoformat() + "Z",
        }
        for row in entries
    ]


@router.get("/admin")
def administration(db: DB, user: Actor):
    if user.id not in settings().admin_user_ids:
        raise HTTPException(404, "Admin dashboard is unavailable.")
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (User, Workspace, Project, Dataset, Job)
    }
