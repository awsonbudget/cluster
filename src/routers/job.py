from fastapi import APIRouter, Depends, UploadFile
from src.internal.type import Resp
from src.internal.cluster import cluster, config, Job
from src.internal.auth import verify_setup
from src.internal.type import Resp, Status
from src.internal.worker import launch
import os
import tarfile


router = APIRouter(tags=["job"])


@router.get("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_ls(node_id: str | None = None) -> Resp:
    """monitoring: 3. cloud job ls [NODE_ID]"""
    rtn = cluster.get_jobs(node_id)
    return Resp(status=True, data=[j.toJSON() for j in rtn])


@router.post("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_launch(job_name: str, job_id: str, job_script: UploadFile) -> Resp:
    """management: 6. cloud launch PATH_TO_JOB"""
    # IMPORTANT: we assume the manager won't create jobs with the same ID!
    if len(cluster.available) == 0:
        return Resp(
            status=False,
            msg=f"cluster: unexpected failure there is no available node",
        )
    node = cluster.available.popleft()
    if node.status != Status.IDLE:
        return Resp(
            status=False,
            msg="cluster: unexpected failure the node is not IDLE",
        )

    script_path = os.path.join("tmp", node.id)
    os.makedirs(script_path, exist_ok=True)
    with open(os.path.join(script_path, f"{job_id}.sh"), "wb") as f:
        f.write(await job_script.read())
    with tarfile.open(os.path.join(script_path, f"{job_id}.tar"), "w") as tar:
        tar.add(os.path.join(script_path, f"{job_id}.sh"))

    job = Job(name=job_name, id=job_id, node=node, status=Status.RUNNING)
    status = node.add_job(job)
    if status == False:
        return Resp(status=False, msg=f"cluster: job id {job_id} already exist")
    status = cluster.add_running(job)
    if status == False:
        return Resp(status=False, msg=f"cluster: job id {job_id} already exist")

    node.status = Status.RUNNING
    launch.delay(job_id, node.id, config["CLUSTER"])

    return Resp(
        status=True,
        msg=f"cluster: job {job_id} launched on node {node.name}",
        data={"node_id": node.id, "node_name": node.name},
    )


@router.delete("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_abort(job_id: str) -> Resp:
    """management: 7. cloud abort JOB_ID"""
    # TODO: abort in Celery as well
    job = cluster.remove_running(job_id)
    if job == None:
        return Resp(status=False, msg="cluster: job not found in the running list")

    job.status = Status.ABORTED
    job.node.status = Status.IDLE
    cluster.available.append(job.node)
    return Resp(status=True, msg=f"cluster: job {job_id} aborted")


@router.get("/cloud/job/log/", dependencies=[Depends(verify_setup)])
async def job_log(job_id: str) -> Resp:
    """monitoring: 4. cloud job log JOB_ID"""
    log = ""
    found = False
    for root, _, files in os.walk("tmp/"):
        for file in files:
            if file == job_id + ".log":
                with open(os.path.join(root, file), "r") as f:
                    log = f.read()
                    found = True
    if not found:
        return Resp(
            status=False, msg=f"cluster: no log found for job {job_id}", data="empty"
        )
    return Resp(status=True, data=log)