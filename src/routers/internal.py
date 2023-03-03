from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.internal.type import Resp
from src.internal.cluster import cluster, config
from src.internal.auth import verify_setup

from src.internal.type import Resp, Status
import requests


router = APIRouter(tags=["internal"])


class Log(BaseModel):
    data: str

## Getting the callback of job completion
@router.post("/internal/callback", dependencies=[Depends(verify_setup)])
async def callback(job_id: str, node_id: str, exit_code: str, log: Log) -> Resp:
    # TODO: Handle None output
    assert config["MANAGER"] != None
    # remove the completed job
    job = cluster.remove_running(job_id)
    if job == None:
        raise Exception(
            f"cluster: job {job_id} received from callback is not in the running list"
        )
    # Mark the job status and node status
    job.status = Status.COMPLETED
    job.node.status = Status.IDLE

    # Add the empty node to the cluster
    cluster.available.append(job.node)

    # Write job log from the callback's output
    with open(f"tmp/{node_id}/{job_id}.log", "w") as f:
        f.write(log.data if log.data else "")

    print(exit_code)
    print(log.data)

    # Notify the manager with the job completion
    requests.post(
        config["MANAGER"] + "/internal/callback/",
        params={"job_id": job_id},
        verify=False,
    )

    return Resp(status=True)

## Get available nodes
@router.get("/internal/available", dependencies=[Depends(verify_setup)])
async def available() -> Resp:
    # Return True as there are IDLE nodes
    if cluster.available and cluster.available[0].status == Status.IDLE:
        return Resp(status=True)
    return Resp(status=False)
