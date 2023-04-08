from fastapi import APIRouter, Depends, UploadFile
from src.internal.cluster import Job
from src.utils.config import cluster, dc, address
from src.internal.auth import verify_setup
from src.internal.type import Resp, JobNodeStatus, JobStatus
import os
import tarfile


router = APIRouter(tags=["job"])


@router.get("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_ls(node_id: str | None = None) -> Resp:
    """monitoring: 3. cloud job ls [NODE_ID]"""
    rtn = cluster.get_jobs_under_node_id(node_id)
    return Resp(status=True, data=[j.toJSON() for j in rtn])


@router.post("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_launch(job_name: str, job_id: str, job_script: UploadFile) -> Resp:
    """management: 6. cloud launch PATH_TO_JOB"""
    # Doing some sanity checks
    assert address["cluster"] != None
    # IMPORTANT: we assume the manager won't create jobs with the same ID!
    if not cluster.has_available_job_nodes():
        return Resp(
            status=False, msg=f"cluster: unexpected failure there is no available node"
        )

    try:
        node = cluster.pop_available_job_node()
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: unexpected failure {e}")

    if node.get_node_status() != JobNodeStatus.IDLE:
        return Resp(
            status=False, msg="cluster: unexpected failure the node is not IDLE"
        )

    # Passed all sanity checks, now we can prepare the job scripts
    script_path = os.path.join("tmp", node.get_node_id())
    os.makedirs(script_path, exist_ok=True)
    with open(os.path.join(script_path, f"{job_id}.sh"), "wb") as f:
        f.write(await job_script.read())
    with open(os.path.join(script_path, "launcher.sh"), "w") as f:
        script = f"""
apt-get update && apt install curl jq -y
chmod +x {script_path+"/"+job_id}.sh
output=$(./{script_path+"/"+job_id}.sh)
exit_code=$?
json_payload=$(echo '{{}}' | jq --arg output "$output" '.data = $output')
curl -X 'POST' "http://host.docker.internal:{address["cluster"].split(":")[2]}/internal/callback?job_id={job_id}&node_id={node.get_node_id()}&exit_code=$exit_code" -H 'accept: application/json' -H 'Content-Type: application/json' -d "$json_payload"
"""
        f.write(script)

    with tarfile.open(os.path.join(script_path, f"{job_id}.tar"), "w") as tar:
        tar.add(os.path.join(script_path, f"{job_id}.sh"))
        tar.add(os.path.join(script_path, "launcher.sh"))

    # Add the job to the cluster
    job = Job(
        job_name=job_name,
        job_id=job_id,
        node_id=node.get_node_id(),
        job_status=JobStatus.RUNNING,
    )
    try:
        node.add_job(job)
        cluster.add_running_job(job)
        node.set_running()
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: unexpected failure {e}")

    # Launch the job in the Docker container
    container = dc.containers.get(node.get_node_id())
    with open(os.path.join(script_path, f"{job_id}.tar"), "rb") as tar:
        container.put_archive("/", tar)  # type: ignore

    launcher = os.path.join(script_path, "launcher.sh")
    container.exec_run(["/bin/bash", "-c", f"chmod +x {launcher}"], detach=True)  # type: ignore
    container.exec_run(["/bin/bash", "-c", f"{launcher}"], detach=True)  # type: ignore

    return Resp(
        status=True,
        msg=f"cluster: job {job_id} launched on node {node.get_node_name()}",
        data={
            "node_id": node.get_node_id(),
            "node_name": node.get_node_name(),
            "pod_id": node.get_pod_id(),
        },
    )


@router.delete("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_abort(job_id: str) -> Resp:
    """management: 7. cloud abort JOB_ID"""
    # TODO: Actually abort the job in the Docker container
    try:
        job = cluster.remove_running_job(job_id)
        job.set_aborted()
        node = cluster.get_node_by_id(job.get_node_id())
        cluster.add_available_job_node(node)
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: {e}")

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
            status=False,
            msg=f"cluster: no log found for job {job_id}",
            data=f"no log found for job {job_id}",
        )
    return Resp(status=True, data=log)
