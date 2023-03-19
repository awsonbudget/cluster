from enum import Enum
from pydantic import BaseModel


class JobNodeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"


class ServerNodeStatus(str, Enum):
    NEW = "new"
    ONLINE = "online"
    PAUSED = "paused"


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
