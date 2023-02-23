from fastapi import APIRouter, Depends
from src.internal.type import Resp
from src.internal.cluster import cluster, config
from src.internal.auth import verify_setup

from src.internal.type import Resp, Status
import requests


router = APIRouter(tags=["internal"])


@router.post("/internal/callback", dependencies=[Depends(verify_setup)])
async def callback(job_id: str, node_id: str, exit_code: str, output: str) -> Resp:
    # TODO: Handle None output
    job = cluster.remove_running(job_id)
    if job == None:
        raise Exception(
            f"cluster: job {job_id} received from callback is not in the running list"
        )

    job.status = Status.COMPLETED
    job.node.status = Status.IDLE

    cluster.available.append(job.node)

    with open(f"tmp/{node_id}/{job_id}.log", "w") as log:
        log.write(output if output else "")

    print(exit_code)
    print(output)

    requests.post(
        config["MANAGER"] + "/internal/callback/",
        params={"job_id": job_id},
        verify=False,
    )

    return Resp(status=True)


@router.get("/internal/available", dependencies=[Depends(verify_setup)])
async def available() -> Resp:
    if cluster.available and cluster.available[0].status == Status.IDLE:
        return Resp(status=True)
    return Resp(status=False)
