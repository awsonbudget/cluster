from __future__ import annotations
from enum import Enum
import tarfile
import docker
import docker.errors
from jobs import launch
from typing import Optional
import shutil
import os
from collections import deque
from fastapi import FastAPI, UploadFile, Request, HTTPException, Depends
from pydantic import BaseModel
import time

app = FastAPI()

dc = docker.from_env()


class Status(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    REGISTERED = "registered"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class Job(object):
    def __init__(self, id: str, name: str, node: Node, status: Status = Status.RUNNING):
        self.id: str = id
        self.name: str = name
        self.node: Node = node
        self.status: Status = status

    def toJSON(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "node": self.node.name,
            "status": self.status,
        }


class Node(object):
    def __init__(self, name: str, id: str):
        self.name: str = name
        self.id: str = id
        self.status = Status.IDLE
        self.jobs: dict[str, Job] = dict()

    def get_job(self, id: str) -> Job | None:
        if id in self.jobs:
            return self.jobs[id]
        return None

    def get_jobs(self) -> list[Job]:
        return list(self.jobs.values())

    def add_job(self, job: Job) -> bool:
        if job.id in self.jobs:
            return False
        self.jobs[job.id] = job
        return True

    def toJSON(self) -> dict:
        return {"name": self.name, "id": self.id, "status": self.status}


class Pod(object):
    def __init__(self, name: str, id: int):
        self.name: str = name
        self.id: int = id
        self.nodes: dict[str, Node] = dict()

    def get_node(self, name: str) -> Node | None:
        if name in self.nodes:
            return self.nodes[name]
        return None

    def get_nodes(self) -> list[Node]:
        return list(self.nodes.values())

    def add_node(self, node: Node) -> bool:
        if node.name in self.nodes:
            return False
        self.nodes[node.name] = node
        return True

    def remove_node(self, name: str) -> Node | None:
        node = self.get_node(name)
        if node == None or node.status != Status.IDLE:
            return None
        return self.nodes.pop(name)

    def toJSON(self) -> dict:
        return {"name": self.name, "id": self.id}


class Cluster(object):
    def __init__(self):
        # The outer dict has pod_name as the key
        # The inner dict has node_name as the key and node_id as the value
        self.pods: dict[str, Pod] = dict()
        self.pod_id: int = 0
        self.running: dict[str, Job] = dict()
        self.nodes: dict[str, Node] = dict()
        self.available: deque[Node] = deque()

    def register_pod(self, name: str) -> bool:
        if name in self.pods:
            return False
        self.pods[name] = Pod(name, self.pod_id)
        self.pod_id += 1
        return True

    def get_pod(self, name: str) -> Pod | None:
        if name in self.pods:
            return self.pods[name]
        return None

    def get_pods(self) -> list[Pod]:
        return list(self.pods.values())

    def remove_pod(self, name: str) -> Pod | None:
        pod = self.get_pod(name)
        if pod == None or len(pod.get_nodes()) != 0:
            return None
        return self.pods.pop(name)

    def add_running(self, job: Job) -> bool:
        if job.id in self.running:
            return False
        self.running[job.id] = job
        return True

    def remove_running(self, job_id: str) -> Job | None:
        return self.running.pop(job_id, None)

    def get_jobs(self, node_name: Optional[str] = None) -> list[Job]:
        rtn = []
        for pod in self.get_pods():
            for node in pod.get_nodes():
                if node_name:
                    if node.name == node_name:
                        rtn.extend(node.get_jobs())
                else:
                    rtn.extend(node.get_jobs())
        return rtn


class Resp(BaseModel):
    status: bool
    msg: str = ""
    data: list | dict | None = None


cluster: Cluster = Cluster()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


async def verify_setup():
    if cluster.get_pod("default") == None:
        raise HTTPException(status_code=400, detail="cluster: please initialize first")


@app.post("/cloud/")
async def init() -> Resp:
    """management: 1. cloud init"""
    if (cluster.get_pod("default")) != None:
        return Resp(status=True, msg="cluster: warning already initialied")

    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu
        cluster.register_pod("default")

        # TODO: do some filtering instead of wiping everything
        for container in dc.containers.list(all=True):
            dc.api.stop(container.id)
            dc.api.remove_container(container.id, force=True)

        try:
            shutil.rmtree("tmp")
        except OSError as e:
            print("tmp was already cleaned")

        return Resp(status=True, msg="cluster: setup completed")

    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg="cluster: docker.errors.APIError")


@app.get("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_ls():
    """monitoring: 1. cloud pod ls"""
    rtn = []
    for pod in cluster.get_pods():
        rtn.append(dict(name=pod.name, id=pod.id, nodes=len(pod.get_nodes())))
    return Resp(status=True, data=rtn)


@app.post("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_register(pod_name: str):
    """management: 2. cloud pod register POD_NAME"""
    status = cluster.register_pod(pod_name)
    if status == True:
        return Resp(status=True, msg=f"cluster: {pod_name} is added as a pod")
    else:
        return Resp(status=False, msg=f"cluster: pod {pod_name} already exists")


@app.delete("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_rm(pod_name: str):
    """management: 3. cloud pod rm POD_NAME"""
    if pod_name == "default":
        return Resp(status=False, msg=f"cluster: you cannot remove the default pod")

    pod = cluster.remove_pod(pod_name)
    if pod:
        return Resp(status=True, msg=f"cluster: {pod_name} is removed from pods")
    else:
        return Resp(
            status=False,
            msg=f"cluster: failed to remove pod {pod_name} because it does not exist or it has nodes inside",
        )


@app.get("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_ls(pod_name: str | None = None) -> Resp:
    """monitoring: 2. cloud node ls [RES_POD_ID]"""
    if pod_name == None:
        rtn = []
        for pod in cluster.get_pods():
            for node in pod.get_nodes():
                rtn.append(
                    dict(
                        name=node.name,
                        id=node.id,
                        status=node.status,
                        pod=pod.toJSON(),
                    )
                )
        return Resp(status=True, data=rtn)

    pod = cluster.get_pod(pod_name)
    if pod == None:
        return Resp(status=False, msg=f"cluster: pod {pod_name} does not exist")

    rtn = []
    for node in pod.get_nodes():
        rtn.append(
            dict(name=node.name, id=node.id, status=node.status, pod=pod.toJSON())
        )
    return Resp(status=True, data=rtn)


@app.post("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_register(node_name: str, pod_name: str | None = None) -> Resp:
    """management: 4. cloud register NODE_NAME [POD_ID]"""
    if pod_name == None:
        pod_name = "default"

    pod = cluster.get_pod(pod_name)
    if pod == None:
        return Resp(status=False, msg=f"cluster: pod {pod_name} does not exist")

    if pod.get_node(node_name) != None:
        return Resp(
            status=False,
            msg=f"cluster: node {node_name} already exist in pod {pod_name}",
        )

    try:
        container = dc.containers.run(
            image="ubuntu",
            name=f"{pod_name}_{node_name}",
            command=["tail", "-f", "/dev/null"],  # keep it running
            detach=True,
        )
        assert container.id != None
        node = Node(name=node_name, id=container.id)
        status = pod.add_node(node)
        cluster.nodes[node.id] = node
        cluster.available.append(node)
        if status:
            return Resp(
                status=True,
                msg=f"cluster: node {node_name} created in pod {pod_name}",
            )
        else:
            return Resp(
                status=False,
                msg=f"cluster: node {node_name} already exist in pod {pod_name}",
            )

    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg=f"cluster: docker.errors.APIError")


@app.delete("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_rm(node_name: str) -> Resp:
    """management: 5. cloud rm NODE_NAME"""
    for pod in cluster.get_pods():
        node = pod.get_node(node_name)
        if node == None:
            continue

        try:
            node = pod.remove_node(node_name)
            if node == None:
                return Resp(
                    status=False,
                    msg=f"cluster: node {node_name} is not IDLE",
                )

            dc.api.remove_container(container=node.id, force=True)
            cluster.nodes.pop(node.id)
            cluster.available.remove(node)
            return Resp(
                status=True,
                msg=f"cluster: node {node_name} removed in pod {pod.name}",
            )
        except docker.errors.APIError as e:
            print(e)
            return Resp(status=False, msg=f"cluster: docker.errors.APIError")

    return Resp(
        status=False,
        msg=f"cluster: node {node_name} does not exist in this cluster",
    )


@app.get("/cloud/job/", dependencies=[Depends(verify_setup)])
async def job_ls(node_id: str | None = None) -> Resp:
    """monitoring: 3. cloud job ls [NODE_ID]"""
    rtn = cluster.get_jobs(node_id)
    return Resp(status=True, data=[j.toJSON() for j in rtn])


@app.post("/cloud/job/", dependencies=[Depends(verify_setup)])
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

    await job_script.close()
    job = Job(name=job_name, id=job_id, node=node, status=Status.RUNNING)
    status = node.add_job(job)
    if status == False:
        return Resp(status=False, msg=f"cluster: job id {job_id} already exist")
    status = cluster.add_running(job)
    if status == False:
        return Resp(status=False, msg=f"cluster: job id {job_id} already exist")

    node.status = Status.RUNNING
    launch.delay(job_id, node.id)

    return Resp(
        status=True,
        msg=f"cluster: job {job_id} launched on node {node.name}",
    )


@app.delete("/cloud/job/", dependencies=[Depends(verify_setup)])
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


@app.get("/cloud/job/log/", dependencies=[Depends(verify_setup)])
async def job_log(job_id: str) -> Resp:
    """monitoring: 4. cloud job log JOB_ID"""
    rtn = dict()
    for root, _, files in os.walk("tmp/"):
        for file in files:
            if file == job_id + ".log":
                with open(os.path.join(root, file), "r") as f:
                    rtn[job_id] = f.read()
    return Resp(status=False, data=rtn)


@app.get("/cloud/node/log/", dependencies=[Depends(verify_setup)])
async def node_log(node_id: str) -> Resp:
    """monitoring: 5. cloud log node NODE_ID"""
    rtn = dict()
    for root, _, files in os.walk("tmp/" + node_id):
        for file in files:
            if file.endswith(".log"):
                with open(os.path.join(root, file), "r") as f:
                    rtn[file[:-4]] = f.read()
    return Resp(status=False, data=rtn)


@app.post("/internal/callback", dependencies=[Depends(verify_setup)])
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

    return Resp(status=True)


@app.get("/internal/available", dependencies=[Depends(verify_setup)])
async def available() -> Resp:
    first = cluster.available[0]
    if first and first.status == Status.IDLE:
        return Resp(status=True, data={"node_id": first.id})
    return Resp(status=False)
