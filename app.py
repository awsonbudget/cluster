from __future__ import annotations
from enum import Enum
import tarfile
from flask import Flask, jsonify, request, Response
from collections import OrderedDict
import docker
import docker.errors
from jobs import launch
from typing import Optional
import shutil
import os

app = Flask(__name__)
app.debug = True

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
        self.nodes.pop(name)
        return node


class Cluster(object):
    def __init__(self):
        # The outer dict has pod_name as the key
        # The inner dict has node_name as the key and node_id as the value
        self.pods: dict[str, Pod] = dict()
        self.pod_id: int = 0
        self.running: dict[str, Job] = dict()
        # the nodes are sorted from available to not available
        self.nodes: OrderedDict[str, Node] = OrderedDict()

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
        return pod

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


cluster: Cluster = Cluster()


@app.route("/cloud/", methods=["POST"])
def init():
    """management: 1. cloud init"""
    if (cluster.get_pod("default")) != None:
        return jsonify(status=True, msg="cluster: warning already initialied")

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

        return jsonify(status=True, msg="cluster: setup completed")

    except docker.errors.APIError as e:
        print(e)
        return jsonify(status=False, msg=f"cluster: docker.errors.APIError")


@app.route("/cloud/pod/", methods=["GET", "POST", "DELETE"])
def pod() -> Response:
    pod_name = request.args.get("pod_name")

    """monitoring: 1. cloud pod ls"""
    if request.method == "GET":
        rtn = []
        for pod in cluster.get_pods():
            rtn.append(dict(name=pod.name, id=pod.id, nodes=len(pod.get_nodes())))
        return jsonify(status=True, data=rtn)

    """management: 2. cloud pod register POD_NAME"""
    if request.method == "POST":
        if pod_name == None:
            return jsonify(status=False, msg=f"cluster: you must specify a pod name")

        status = cluster.register_pod(pod_name)
        if status == True:
            return jsonify(status=True, msg=f"cluster: {pod_name} is added as a pod")
        else:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} already exists")

    """management: 3. cloud pod rm POD_NAME"""
    if request.method == "DELETE":
        if pod_name == None:
            return jsonify(status=False, msg=f"cluster: you must specify a pod name")
        if pod_name == "default":
            return jsonify(
                status=False, msg=f"cluster: you cannot remove the default pod"
            )

        pod = cluster.remove_pod(pod_name)
        if pod:
            return jsonify(status=True, msg=f"cluster: {pod_name} is removed from pods")
        else:
            return jsonify(
                status=False,
                msg=f"cluster: failed to remove pod {pod_name} because it does not exist or it has nodes inside",
            )

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/node/", methods=["GET", "POST", "DELETE"])
def node() -> Response:
    node_name = request.args.get("node_name")
    pod_name = request.args.get("pod_name")

    """monitoring: 2. cloud node ls [RES_POD_ID]"""
    if request.method == "GET":
        if pod_name == None:
            rtn = []
            for pod in cluster.get_pods():
                for node in pod.get_nodes():
                    rtn.append(dict(name=node.name, id=node.id, status=node.status))
            return jsonify(status=True, data=rtn)

        pod = cluster.get_pod(pod_name)
        if pod == None:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")

        rtn = []
        for node in pod.get_nodes():
            rtn.append(dict(name=node.name, id=node.id, status=node.status))
        return jsonify(status=True, data=rtn)

    """management: 4. cloud register NODE_NAME [POD_ID]"""
    if request.method == "POST":
        if node_name == None:
            return jsonify(status=False, msg=f"cluster: you must specify a node name")

        if pod_name == None:
            pod_name = "default"

        pod = cluster.get_pod(pod_name)
        if pod == None:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")

        if pod.get_node(node_name) != None:
            return jsonify(
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
            if status:
                return jsonify(
                    status=True,
                    msg=f"cluster: node {node_name} created in pod {pod_name}",
                )
            else:
                return jsonify(
                    status=False,
                    msg=f"cluster: node {node_name} already exist in pod {pod_name}",
                )

        except docker.errors.APIError as e:
            print(e)
            return jsonify(status=False, msg=f"cluster: docker.errors.APIError")

    """management: 5. cloud rm NODE_NAME"""
    if request.method == "DELETE":
        if node_name == None:
            return jsonify(status=False, msg=f"cluster: you must specify a node name")

        for pod in cluster.get_pods():
            node = pod.get_node(node_name)
            if node == None:
                continue

            try:
                node = pod.remove_node(node_name)
                if node == None:
                    return jsonify(
                        status=False,
                        msg=f"cluster: node {node_name} is not IDLE",
                    )

                dc.api.remove_container(container=node.id, force=True)
                cluster.nodes.pop(node.id)
                return jsonify(
                    status=True,
                    msg=f"cluster: node {node_name} removed in pod {pod_name}",
                )
            except docker.errors.APIError as e:
                print(e)
                return jsonify(status=False, msg=f"cluster: docker.errors.APIError")

        return jsonify(
            status=False,
            msg=f"cluster: node {node_name} does not exist in this cluster",
        )

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/job/", methods=["GET", "POST", "DELETE"])
def job() -> Response:
    """monitoring: 3. cloud job ls [NODE_ID]"""
    if request.method == "GET":
        node_id = request.args.get("node_id")
        rtn = cluster.get_jobs(node_id)
        return jsonify(status=True, data=[j.toJSON() for j in rtn])

    """management: 6. cloud launch PATH_TO_JOB"""
    if request.method == "POST":
        # IMPORTANT: we assume the manager won't create jobs with the same ID!
        job_name = request.args.get("job_name")
        if job_name == None:
            return jsonify(status=False, msg="cluster: unknown job name")
        job_id = request.args.get("job_id")
        if job_id == None:
            return jsonify(status=False, msg="cluster: unknown job id")
        job_script = request.files.get("job_script")
        if job_script == None:
            return jsonify(status=False, msg="cluster: you need to attach a script")
        node_id = request.args.get("node_id")
        if node_id == None:
            return jsonify(
                status=False, msg="cluster: you need to specify a node to run the job"
            )

        node = cluster.nodes.get(node_id, None)
        if node == None:
            return jsonify(
                status=False,
                msg=f"cluster: unexpected failure the chosen node {node_id} does not exist",
            )

        # Reorder move unavailable to the end
        cluster.nodes.move_to_end(node_id, last=True)

        if node.status != Status.IDLE:
            return jsonify(
                status=False,
                msg="cluster: unexpected failure the chosen node is not IDLE",
            )

        script_path = os.path.join("tmp", node.id)
        os.makedirs(script_path, exist_ok=True)
        with open(os.path.join(script_path, f"{job_id}.sh"), "wb") as f:
            f.write(job_script.read())
        with tarfile.open(os.path.join(script_path, f"{job_id}.tar"), "w") as tar:
            tar.add(os.path.join(script_path, f"{job_id}.sh"))

        job = Job(name=job_name, id=job_id, node=node, status=Status.RUNNING)
        status = node.add_job(job)
        if status == False:
            return jsonify(status=False, msg=f"cluster: job id {job_id} already exist")
        status = cluster.add_running(job)
        if status == False:
            return jsonify(status=False, msg=f"cluster: job id {job_id} already exist")

        node.status = Status.RUNNING
        launch.delay(job_id, node.id)

        return jsonify(
            status=True,
            msg=f"cluster: job {job_id} launched on node {node.name}",
        )

    """management: 7. cloud abort JOB_ID"""
    if request.method == "DELETE":
        job_id = request.args.get("job_id")
        if job_id == None:
            return jsonify(status=False, msg="cluster: unknown job id")

        job = cluster.remove_running(job_id)
        if job == None:
            return jsonify(
                status=False, msg="cluster: job not found in the running list"
            )

        job.status = Status.ABORTED
        job.node.status = Status.IDLE
        return jsonify(status=True, msg=f"cluster: job {job_id} aborted")

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/log/", methods=["GET"])
def log() -> Response:
    """monitoring: 4. cloud job log JOB_ID"""
    """monitoring: 5. cloud log node NODE_ID"""
    if request.method == "GET":
        job_id = request.args.get("job_id")
        node_id = request.args.get("node_id")

        if job_id == None and node_id == None:
            return jsonify(
                status=False, msg="cluster: you need to specify a node_id or a job_id"
            )

        if job_id:
            rtn = dict()
            for root, _, files in os.walk("tmp/"):
                for file in files:
                    if file == job_id + ".log":
                        with open(os.path.join(root, file), "r") as f:
                            rtn[job_id] = f.read()
            return jsonify(status=False, data=rtn)

        if node_id:
            rtn = dict()
            for root, _, files in os.walk("tmp/" + node_id):
                for file in files:
                    if file.endswith(".log"):
                        with open(os.path.join(root, file), "r") as f:
                            rtn[job_id] = f.read()
            return jsonify(status=False, data=rtn)

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/internal/callback", methods=["POST"])
def callback() -> Response:
    job_id = request.args.get("job_id")
    node_id = request.args.get("node_id")
    exit_code = request.args.get("exit_code")
    output = request.args.get("output")

    if job_id == None:
        raise Exception("cluster: received an unknown job_id from callback")
    if node_id == None:
        raise Exception("cluster: received an unknown node_id from callback")

    job = cluster.remove_running(job_id)
    if job == None:
        raise Exception(
            f"cluster: job {job_id} received from callback is not in the running list"
        )

    job.status = Status.COMPLETED
    job.node.status = Status.IDLE

    # move the available node to the beginning
    cluster.nodes.move_to_end(node_id, last=False)

    with open(f"tmp/{node_id}/{job_id}.log", "w") as log:
        log.write(output if output else "")

    print(exit_code)
    print(output)

    return Response(status=204)


@app.route("/internal/available", methods=["GET"])
def available() -> Response:
    first = next(iter(cluster.nodes.values()))
    if first.status == Status.IDLE:
        return jsonify(status=True, node_id=first.id)
    return jsonify(status=False, node_id="")


if __name__ == "__main__":
    app.run(port=5551)
