from fastapi import APIRouter, Depends, UploadFile
from src.internal.type import Resp
from src.internal.cluster import cluster, config, Job, dc
from src.internal.auth import verify_setup
from src.internal.type import Resp, Status
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
    # Doing some sanity checks
    assert config["CLUSTER"] != None
    # IMPORTANT: we assume the manager won't create jobs with the same ID!
    if len(cluster.available) == 0:
        return Resp(
            status=False,
            msg=f"cluster: unexpected failure there is no available node",
        )
    # Get one available node from the queue
    node = cluster.available.popleft()
    # If the left-side is even unavailable, that means all the nodes are working now
    if node.status != Status.IDLE:
        return Resp(
            status=False,
            msg="cluster: unexpected failure the node is not IDLE",
        )

    # Passed all sanity checks, now we can prepare the job scripts
    script_path = os.path.join("tmp", node.id)
    os.makedirs(script_path, exist_ok=True)
    with open(os.path.join(script_path, f"{job_id}.sh"), "wb") as f:
        f.write(await job_script.read())
    # Write launcher.sh to control the execution of jobs
    with open(os.path.join(script_path, "launcher.sh"), "w") as f:
        script = f"""
apt-get update && apt install curl jq -y
chmod +x {script_path+"/"+job_id}.sh
output=$(./{script_path+"/"+job_id}.sh)
exit_code=$?
json_payload=$(echo '{{}}' | jq --arg output "$output" '.data = $output')
curl -X 'POST' "http://host.docker.internal:{config["CLUSTER"].split(":")[2]}/internal/callback?job_id={job_id}&node_id={node.id}&exit_code=$exit_code" -H 'accept: application/json' -H 'Content-Type: application/json' -d "$json_payload"
"""
        f.write(script)

    # Pack the job and launcher for passing to the container
    with tarfile.open(os.path.join(script_path, f"{job_id}.tar"), "w") as tar:
        tar.add(os.path.join(script_path, f"{job_id}.sh"))
        tar.add(os.path.join(script_path, "launcher.sh"))

    # Add the job to the cluster
    job = Job(name=job_name, id=job_id, node=node, status=Status.RUNNING)
    status = node.add_job(job)
    if status == False:
        return Resp(status=False, msg=f"cluster: job id {job_id} already exist")
    # Check if the job has been launched 
    status = cluster.add_running(job)
    if status == False:
        return Resp(status=False, msg=f"cluster: job id {job_id} already exist")

    node.status = Status.RUNNING

    # Launch the job in the Docker container
    container = dc.containers.get(node.id)
    with open(os.path.join(script_path, f"{job_id}.tar"), "rb") as tar:
        container.put_archive("/", tar)

    # Execute the job in the container
    launcher = os.path.join(script_path, "launcher.sh")
    container.exec_run(["/bin/bash", "-c", f"chmod +x {launcher}"], detach=True)
    container.exec_run(["/bin/bash", "-c", f"{launcher}"], detach=True)

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

    # Mark the job status and node status
    job.status = Status.ABORTED
    job.node.status = Status.IDLE
    cluster.available.append(job.node)
    return Resp(status=True, msg=f"cluster: job {job_id} aborted")

## Get the job log
@router.get("/cloud/job/log/", dependencies=[Depends(verify_setup)])
async def job_log(job_id: str) -> Resp:
    """monitoring: 4. cloud job log JOB_ID"""
    log = ""
    found = False
    for root, _, files in os.walk("tmp/"):
        for file in files:
            # Find the log file and record the log
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
