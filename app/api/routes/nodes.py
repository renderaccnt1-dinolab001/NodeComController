from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
import uuid
from typing import Optional
from sqlmodel import Session, select
from app.services.db import get_session
from app.models import Account, ComputeNode, Group, Task
from app.services.group_manager import create_group_for_task, assign_worker_to_group

router = APIRouter()


class RegisterNodeRequest(BaseModel):
    google_auth_token: str
    url_addr: str
    dashboard_url: Optional[str] = None  # Node's dashboard server URL (port 9004)


@router.post("/register")
async def register_node(request: RegisterNodeRequest, session: Session = Depends(get_session)):
    """
    Validates Google Auth token, upserts account and node, assigns group/role.
    Returns session_token, role, and (if worker) the leader URL.
    """
    # 1. Verify token with Google.
    #    Colab's auth flow may produce either an OIDC ID token (JWT) or a plain
    #    OAuth2 access token.  The two tokeninfo params are different, so we
    #    try id_token first and fall back to access_token.
    token_info = None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={request.google_auth_token}"
            )
            if resp.status_code == 200:
                token_info = resp.json()
            else:
                # Fall back to access_token verification
                resp2 = await client.get(
                    f"https://oauth2.googleapis.com/tokeninfo?access_token={request.google_auth_token}"
                )
                if resp2.status_code == 200:
                    token_info = resp2.json()
                else:
                    raise HTTPException(
                        status_code=401,
                        detail=f"Google rejected the token as both an ID token and an access token. "
                               f"id_token status: {resp.status_code}, "
                               f"access_token status: {resp2.status_code}.",
                    )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify token: {str(e)}")

    sub = token_info.get("sub")
    gmail = token_info.get("email")

    if not sub:
        raise HTTPException(status_code=400, detail="Token missing subject (sub)")

    session_token = str(uuid.uuid4())

    # 2. Upsert Account
    account = session.get(Account, sub)
    if not account:
        account = Account(id=sub, gmail=gmail)
        session.add(account)
    else:
        account.gmail = gmail

    # 3. Upsert ComputeNode
    node = session.get(ComputeNode, sub)
    if not node:
        node = ComputeNode(
            id=sub,
            url_addr=request.url_addr,
            dashboard_url=request.dashboard_url,
            account_id=sub,
            session_token=session_token,
            status="IDLE",
        )
        session.add(node)
    else:
        node.url_addr = request.url_addr
        node.dashboard_url = request.dashboard_url
        node.session_token = session_token
        node.status = "IDLE"
        node.group_id = None  # reset group on re-register

    session.commit()
    session.refresh(node)

    # 4. Group Allocation Logic
    # Look for a pending task that has no group yet
    pending_task = session.exec(
        select(Task).where(Task.global_State == "PENDING").outerjoin(
            Group, Group.task_id == Task.id
        ).where(Group.id == None)  # noqa: E711
    ).first()

    if pending_task:
        # No group exists for this task — make this node the leader
        group = create_group_for_task(pending_task.id, node, session)
        session.commit()
        session.refresh(group)

        return {
            "status": "success",
            "role": "LEADER",
            "session_token": session_token,
            "group_token": group.group_token,
            "group_id": group.id,
            "task_id": pending_task.id,
            "github_repo_url": pending_task.github_repo_url,
            "global_TCB": pending_task.global_TCB,
        }
    else:
        # Look for an existing active group that needs more workers
        existing_group = session.exec(
            select(Group).where(Group.task_id != None)  # noqa: E711
        ).first()

        if existing_group:
            leader_node = session.get(ComputeNode, existing_group.group_lead)
            assign_worker_to_group(existing_group, node, session)
            session.commit()

            return {
                "status": "success",
                "role": "WORKER",
                "session_token": session_token,
                "group_token": existing_group.group_token,
                "group_id": existing_group.id,
                "leader_url": leader_node.url_addr if leader_node else None,
            }
        else:
            # No active tasks — node sits idle
            return {
                "status": "success",
                "role": "IDLE",
                "session_token": session_token,
                "message": "No active tasks. Node registered as idle.",
            }
