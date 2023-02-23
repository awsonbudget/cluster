from enum import Enum
from pydantic import BaseModel


class Status(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    REGISTERED = "registered"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class Resp(BaseModel):
    status: bool
    msg: str = ""
    data: list | dict | str | None = None
