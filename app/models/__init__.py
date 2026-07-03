from typing import Optional, Dict, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column, JSON
import uuid


class Account(SQLModel, table=True):
    __tablename__ = "account"

    id: str = Field(primary_key=True)  # Google OAuth 'sub'
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    gmail: Optional[str] = None
    score: Optional[int] = Field(default=0)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    global_TCB: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    global_State: Optional[str] = None
    github_repo_url: Optional[str] = None
    created_by: Optional[str] = Field(default=None, foreign_key="account.id")


class StorageDrive(SQLModel, table=True):
    __tablename__ = "storage_drives"

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    drive_id: str
    credentials: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    capacity: Optional[int] = None
    remaining_space: Optional[int] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class DriveAssignment(SQLModel, table=True):
    __tablename__ = "drive_assignments"

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id")
    drive_id: Optional[str] = Field(default=None, foreign_key="storage_drives.id")
    folder_path: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Group(SQLModel, table=True):
    __tablename__ = "groups"

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: Optional[str] = Field(default=None, foreign_key="tasks.id")
    group_lead: Optional[str] = None  # FK to ComputeNodes set post-creation
    group_token: Optional[str] = None


class ComputeNode(SQLModel, table=True):
    __tablename__ = "ComputeNodes"

    id: str = Field(primary_key=True)  # Google OAuth 'sub'
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    url_addr: Optional[str] = None
    dashboard_url: Optional[str] = None  # Node's dashboard server URL (port 9004)
    account_id: Optional[str] = Field(default=None, foreign_key="account.id")
    group_id: Optional[str] = Field(default=None, foreign_key="groups.id")
    status: Optional[str] = Field(default="IDLE")
    session_token: Optional[str] = None


class TaskSnapshot(SQLModel, table=True):
    __tablename__ = "task_snapshot"

    timestamp: datetime = Field(default_factory=datetime.utcnow, primary_key=True)
    node_id: Optional[str] = Field(default=None, foreign_key="ComputeNodes.id")
    TCB_snapshot: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    sender_id: Optional[str] = Field(default=None, foreign_key="account.id")
    receiver_id: Optional[str] = Field(default=None, foreign_key="account.id")
    amount: int
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)
