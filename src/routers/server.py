from fastapi import APIRouter, Depends
from src.utils.config import cluster, dc, address
from src.internal.auth import verify_setup
from src.internal.type import Resp, ServerNodeStatus, JobStatus


router = APIRouter(tags=["server"])


@router.post("/cloud/server/launch/", dependencies=[Depends(verify_setup)])
async def server_launch(pod_id: str) -> Resp:
    """cloud server launch POD_ID"""
    return Resp(status=False)


@router.post("/cloud/server/resume/", dependencies=[Depends(verify_setup)])
async def server_resume(pod_id: str) -> Resp:
    """cloud server resume PDO_ID"""
    return Resp(status=False)


@router.post("/cloud/server/pause/", dependencies=[Depends(verify_setup)])
async def server_pause(pod_id: str) -> Resp:
    """cloud server launch POD_ID"""
    return Resp(status=False)
