from enum import Enum
from pydantic import BaseModel


class NodeStatus(str, Enum):
    IDLE = "idle"
    NEW = "new"
    RUNNING = "running"


class JobStatus(str, Enum):
    REGISTERED = "registered"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class Resp(BaseModel):
    status: bool
    msg: str = ""
    data: list | dict | str | None = None
