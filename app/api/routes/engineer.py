"""
Engineer Dashboard API routes.

Endpoints:
  POST /api/engineer/login         — issue a JWT for an engineer (name-only auth for now)
  GET  /api/engineer/leader-info   — return the leader for a SPECIFIC task (task_id required)
  GET  /api/engineer/task-status   — poll the state of a specific task
"""
from fastapi import APIRouter, HTTPException, Header, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select
import jwt

from app.services.db_session import get_session
from app.services.engineer_auth import create_engineer_token, verify_engineer_token
from app.models import ComputeNode, Group, Task

router = APIRouter()


# ─── Auth dependency ──────────────────────────────────────────────────────────

def get_engineer_payload(authorization: str = Header(None)) -> dict:
    """FastAPI dependency: extract and verify engineer JWT from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        return verify_engineer_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Engineer token has expired")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid engineer token: {e}")


# ─── Routes ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    name: str


@router.post("/login")
def engineer_login(request: LoginRequest):
    """
    Issue a JWT for an engineer.
    No password required for now — just a display name.
    Multiple engineers can be logged in simultaneously, each with their own token.
    """
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    token = create_engineer_token(request.name.strip())
    return {
        "status": "ok",
        "engineer_name": request.name.strip(),
        "engineer_token": token,
    }


@router.get("/leader-info")
def get_leader_info(
    task_id: str = Query(..., description="The task_id returned by POST /api/tasks/create"),
    engineer: dict = Depends(get_engineer_payload),
    session: Session = Depends(get_session),
):
    """
    Returns the leader node for a SPECIFIC task.

    This is intentionally task-scoped to prevent a bug where multiple engineers
    each creating separate tasks could all be directed to the same leader node.

    Each task has at most one leader node via its Group record.
    Returns 404 if no leader exists yet (task still PENDING / PENDING_UPLOAD).
    """
    # Find the task
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Find the group for this task
    group = session.exec(
        select(Group).where(Group.task_id == task_id)
    ).first()

    if not group:
        raise HTTPException(
            status_code=404,
            detail="No group (and therefore no leader) assigned to this task yet. "
                   "A node must connect and register before a leader is assigned.",
        )

    # Verify the leader node exists and is actually LEADER
    leader_node = session.get(ComputeNode, group.group_lead) if group.group_lead else None
    if not leader_node or leader_node.status != "LEADER":
        raise HTTPException(
            status_code=404,
            detail="Leader node for this task is not active. "
                   "It may have disconnected — check node status.",
        )

    return {
        "engineer_name": engineer.get("sub"),
        "task_id": task_id,
        "task_state": task.global_State,
        "group_id": group.id,
        "leader_node_id": leader_node.id,
        "leader_url": leader_node.url_addr,
        "leader_dashboard_url": leader_node.dashboard_url,
    }


@router.get("/task-status")
def get_task_status(
    task_id: str = Query(..., description="The task_id to poll"),
    engineer: dict = Depends(get_engineer_payload),
    session: Session = Depends(get_session),
):
    """
    Lightweight poll endpoint — returns just the task state and whether a
    leader exists yet. The dashboard uses this to know when to switch from
    the 'waiting for node' screen to the upload/live view.
    """
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    group = session.exec(select(Group).where(Group.task_id == task_id)).first()
    leader_ready = False
    leader_dashboard_url = None

    if group and group.group_lead:
        leader_node = session.get(ComputeNode, group.group_lead)
        if leader_node and leader_node.status == "LEADER":
            leader_ready = True
            leader_dashboard_url = leader_node.dashboard_url

    return {
        "task_id": task_id,
        "task_state": task.global_State,
        "leader_ready": leader_ready,
        "leader_dashboard_url": leader_dashboard_url,
    }
