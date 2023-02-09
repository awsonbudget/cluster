from __future__ import annotations
from enum import Enum
import tarfile
from flask import Flask, jsonify, request, Response
import docker
import docker.errors
from jobs import launch
from typing import Optional

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

    def toJSON(self):
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

    def add_job(self, job: Job):
        self.jobs[job.id] = job

    def toJSON(self):
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

    def add_node(self, node: Node):
        assert node.name not in self.nodes
        self.nodes[node.name] = node

    def remove_node(self, name: str) -> Node | None:
        if self.get_node(name) != None:
            return self.nodes.pop(name)


class Cluster(object):
    def __init__(self):
        # The outer dict has pod_name as the key
        # The inner dict has node_name as the key and node_id as the value
        self.pods: dict[str, Pod] = dict()
        self.pod_id: int = 0
        self.running: dict[str, Job] = dict()

    def register_pod(self, name: str):
        self.pods[name] = Pod(name, self.pod_id)  # Init the "default" pod
        self.pod_id += 1

    def get_pod(self, name: str) -> Pod | None:
        if name in self.pods:
            return self.pods[name]
        return None

    def get_pods(self) -> list[Pod]:
        return list(self.pods.values())

    def remove_pod(self, name: str) -> Pod | None:
        if name in self.pods:
            return self.pods.pop(name)
        return None

    def add_running(self, job: Job):
        self.running[job.id] = job

    def get_jobs(self, node_name: Optional[str] = None) -> list[Job]:
        for pod in self.get_pods():
            if node_name != None:
                node = pod.get_node(node_name)
                if node == None:
                    raise Exception(f"node {node_name} does not exist")
                return node.get_jobs()
            else:
                rtn: list[Job] = []
                for node in pod.get_nodes():
                    rtn.extend(node.get_jobs())
                return rtn
        raise Exception("what the hell is happening")


cluster: Cluster = Cluster()


@app.route("/cloud/", methods=["POST"])
def init():
    """management: 1. cloud init"""
    if (cluster.get_pod("default")) != None:
        return jsonify(status=True, msg="cluster: warning already initialied")

    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu
        cluster.register_pod("default")
        # Let's wipe all containers at startup
        # TODO: do some filtering instead of wiping everything
        for container in dc.containers.list(all=True):
            dc.api.stop(container.id)
            dc.api.remove_container(container.id, force=True)
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
        for pod in cluster.pods.values():
            rtn.append(dict(name=pod.name, id=pod.id, nodes=len(pod.nodes)))
        return jsonify(status=True, data=rtn)

    """management: 2. cloud pod register POD_NAME"""
    if request.method == "POST":
        if pod_name == None:
            return jsonify(status=False, msg=f"cluster: you must specify a pod name")

        if cluster.get_pod(pod_name) != None:
            return jsonify(
                status=False, msg=f"cluster: {pod_name} is already a pod in pods"
            )

        cluster.register_pod(pod_name)
        return jsonify(status=True, msg=f"cluster: {pod_name} is added as a pod")

    """management: 3. cloud pod rm POD_NAME"""
    if request.method == "DELETE":
        # TODO: check for instances before removing
        if pod_name == None:
            return jsonify(status=False, msg=f"cluster: you must specify a pod name")

        rtn = cluster.remove_pod(pod_name)
        if rtn == None:
            return jsonify(
                status=False, msg=f"cluster: {pod_name} is not a pod in pods"
            )
        return jsonify(status=True, msg=f"cluster: {pod_name} is removed from pods")

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/node/", methods=["GET", "POST", "DELETE"])
def node() -> Response:
    node_name = request.args.get("node_name")
    pod_name = request.args.get("pod_name")

    """monitoring: 2. cloud node ls [RES_POD_ID]"""
    if request.method == "GET":
        if pod_name == None:
            rtn = []
            for pod in cluster.pods.values():
                for node in pod.nodes.values():
                    rtn.append(dict(name=node.name, id=node.id, status=node.status))
            return jsonify(status=True, data=rtn)

        pod = cluster.get_pod(pod_name)
        if pod == None:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")

        rtn = []
        for node in pod.nodes.values():
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
                command=["tail", "-f", "/dev/null"],
                detach=True,
                # tty=True,
            )
            assert container.id != None
            node = Node(name=node_name, id=container.id)
            pod.add_node(node)
            return jsonify(
                status=True,
                msg=f"cluster: node {node_name} created in pod {pod_name}",
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
                dc.api.remove_container(container=node.id)
                pod.remove_node(node_name)
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
        # TODO: don't create job with duplicated id
        job_name = request.args.get("job_name")
        if job_name == None:
            return jsonify(status=False, msg="cluster: unknown job name")
        job_id = request.args.get("job_id")
        if job_id == None:
            return jsonify(status=False, msg="cluster: unknown job id")
        job_script = request.files.get("job_script")
        if job_script == None:
            return jsonify(status=False, msg="cluster: you need to attach a script")

        for pods in cluster.get_pods():
            for node in pods.get_nodes():
                if node.status == Status.IDLE:
                    job = Job(
                        name=job_name, id=job_id, node=node, status=Status.RUNNING
                    )
                    node.add_job(job)
                    print(node.jobs)
                    node.status = Status.RUNNING
                    cluster.add_running(job)
                    print("strat trying")
                    with open(f"tmp/{job_id}.sh", "wb") as f:
                        f.write(job_script.read())
                    with tarfile.open(f"tmp/{job_id}.tar", "w") as tar:
                        tar.add(f"tmp/{job_id}.sh")
                    try:
                        launch.delay(job_id, node.id)

                        return jsonify(
                            status=True, msg=f"cluster: job {job_id} launched"
                        )
                    # # TODO: This is not right
                    # with open("tmp/script.sh", "wb") as f:
                    #     f.write(job_script.read())
                    # with tarfile.open("tmp/script.tar", "w") as tar:
                    #     tar.add("tmp/script.sh")
                    # with open("tmp/script.tar", "rb") as tar:
                    #     container = dc.containers.get(node.id)
                    #     container.put_archive("/tmp/", tar)
                    #     container.exec_run(
                    #         ["/bin/bash", "-c", "chmod +x /tmp/script.sh"]
                    #     )
                    #     output = container.exec_run(
                    #         ["/bin/bash", "-c", "/tmp/script.sh"]
                    #     )
                    #     if output.exit_code == 0:
                    #         return jsonify(status=True)
                    #     return jsonify(status=False)

                    except docker.errors.APIError as e:
                        print(e)
                        job.status = Status.FAILED
                        node.status = Status.IDLE
                        return jsonify(
                            status=False, msg=f"cluster: docker.errors.APIError"
                        )

        return jsonify(status=False, msg="cluster: unexpected failure on allocation")

    """management: 7. cloud abort JOB_ID"""
    if request.method == "DELETE":
        job_id = request.args.get("job_id")
        if job_id == None:
            return jsonify(status=False, msg="cluster: unknown job id")

        job = cluster.running.get(job_id, None)
        if job == None:
            return jsonify(status=False, msg="cluster: job not found")

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

        if node_id:
            # TODO: retrive the log here
            pass

        if job_id:
            # TODO: retrive the log here
            pass

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/callback", methods=["POST"])
def callback() -> Response:
    job_id = request.args.get("job_id")
    exit_code = request.args.get("exit_code")
    output = request.args.get("output")
    if job_id == None:
        return jsonify(status=False, msg="cluster: unknown job id")

    job = cluster.running.get(job_id, None)
    if job == None:
        return jsonify(status=False, msg="cluster: job not found")

    job.status = Status.COMPLETED
    job.node.status = Status.IDLE
    cluster.running.pop(job_id)
    print(exit_code, output)
    return jsonify(status=True, msg=f"cluster: job {job_id} aborted")


if __name__ == "__main__":
    app.run(port=5551)
