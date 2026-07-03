"""
Group manager — shared helper for creating groups and assigning node roles.

Used by both:
  - nodes.py  (at register time, when a pending task already exists)
  - node_notifier.py  (after task creation, pushing to idle nodes)

This ensures both paths produce identical DB state.
"""
import uuid
from sqlmodel import Session
from app.models import Group, ComputeNode, Task


def create_group_for_task(task_id: str, leader_node: ComputeNode, session: Session) -> Group:
    """
    Create a new Group for the given task, designate leader_node as the group lead.
    Updates leader_node.status = "LEADER" and group_id in place (does not commit).
    Caller is responsible for session.commit().
    """
    group_token = str(uuid.uuid4())
    group = Group(
        task_id=task_id,
        group_lead=leader_node.id,
        group_token=group_token,
    )
    session.add(group)
    session.flush()  # populate group.id without full commit

    leader_node.group_id = group.id
    leader_node.status = "LEADER"
    session.add(leader_node)

    return group


def assign_worker_to_group(group: Group, worker_node: ComputeNode, session: Session) -> None:
    """
    Assign an existing idle node as a WORKER in the given group.
    Does not commit — caller is responsible.
    """
    worker_node.group_id = group.id
    worker_node.status = "WORKER"
    session.add(worker_node)
