"""
Node notifier — pushes role assignments to idle compute nodes.

Called after a new task is created. Queries all IDLE nodes, assigns the first
as LEADER (creating a Group), and the rest as WORKERs. POSTs to each node's
stored url_addr using their session_token for auth.

Nodes that are unreachable are marked DISCONNECTED.
"""
import httpx
from sqlmodel import Session, select
from app.models import ComputeNode, Task
from app.services.group_manager import create_group_for_task, assign_worker_to_group
from app.core.config import settings


async def notify_idle_nodes(task: Task, session: Session) -> str | None:
    """
    Assigns idle nodes to the task and notifies them via HTTP push.

    Returns the leader's dashboard_url, or None if no idle nodes were found.
    """
    idle_nodes = session.exec(
        select(ComputeNode).where(ComputeNode.status == "IDLE")
    ).all()

    if not idle_nodes:
        return None

    leader_node = idle_nodes[0]
    worker_nodes = idle_nodes[1:]

    # Create the group with this node as leader
    group = create_group_for_task(task.id, leader_node, session)

    # Assign all remaining idle nodes as workers
    for worker in worker_nodes:
        assign_worker_to_group(group, worker, session)

    session.commit()
    session.refresh(group)
    session.refresh(leader_node)

    async with httpx.AsyncClient(timeout=5.0) as client:
        # ── Push to leader ────────────────────────────────────────────────────
        leader_payload = {
            "role": "LEADER",
            "group_id": group.id,
            "group_token": group.group_token,
            "task_id": task.id,
            "github_repo_url": task.github_repo_url,
            "global_TCB": task.global_TCB,
            "engineer_jwt_secret": settings.ENGINEER_JWT_SECRET,
        }
        if not await _push_to_node(client, leader_node, leader_payload, session):
            leader_node.status = "DISCONNECTED"
            session.add(leader_node)
            session.commit()
            return None

        # ── Push to each worker ───────────────────────────────────────────────
        for worker in worker_nodes:
            worker_payload = {
                "role": "WORKER",
                "group_id": group.id,
                "group_token": group.group_token,
                "leader_url": leader_node.url_addr,
            }
            if not await _push_to_node(client, worker, worker_payload, session):
                worker.status = "DISCONNECTED"
                session.add(worker)

        session.commit()

    return leader_node.dashboard_url


async def _push_to_node(
    client: httpx.AsyncClient,
    node: ComputeNode,
    payload: dict,
    session: Session,
) -> bool:
    """
    POST payload to /controller/update-role on the node.
    Returns True on success, False if unreachable.
    """
    if not node.url_addr or not node.session_token:
        return False
    try:
        resp = await client.post(
            f"{node.url_addr}/controller/update-role",
            json=payload,
            headers={"x-session-token": node.session_token},
        )
        return resp.status_code == 200
    except Exception as exc:
        print(f"[NodeNotifier] Failed to push to node {node.id}: {exc}")
        return False
