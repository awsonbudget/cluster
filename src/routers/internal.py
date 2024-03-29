import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.internal.cluster import ServerNode
from src.internal.type import Resp
from src.utils.config import cluster, address
from src.internal.auth import verify_setup


router = APIRouter(tags=["internal"])


class Log(BaseModel):
    data: str


@router.post("/internal/callback", dependencies=[Depends(verify_setup)])
async def callback(job_id: str, node_id: str, exit_code: str, log: Log) -> Resp:
    # TODO: Handle None output
    assert address["manager"] != None
    job = cluster.remove_running_job(job_id)
    if job == None:
        raise Exception(
            f"cluster: job {job_id} received from callback is not in the running list"
        )

    job.set_completed()
    node = cluster.get_node_by_id(job.get_node_id())
    if node == None:
        raise Exception(f"cluster: node {job.get_node_id()} does not exist")
    if isinstance(node, ServerNode):
        raise Exception(f"cluster: node {job.get_node_id()} is not a job node")

    node.set_idle()
    cluster.add_available_job_node(node)

    with open(f"tmp/{node_id}/{job_id}.log", "w") as f:
        f.write(log.data if log.data else "")

    async with httpx.AsyncClient() as client:
        r = await client.post(
            address["manager"] + "/internal/callback/",
            params={"job_id": job_id},
        )
        print(r)

    return Resp(status=True)


@router.get("/internal/available", dependencies=[Depends(verify_setup)])
async def available() -> Resp:
    return Resp(status=cluster.has_available_job_nodes())
