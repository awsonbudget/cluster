from enum import Enum
from flask import Flask, jsonify, request, Response
import docker
import docker.errors
import uuid

app = Flask(__name__)
app.debug = True

dc = docker.from_env()


class Status(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    REGISTERED = "registered"
    COMPLETED = "completed"
    ABORTED = "aborted"


class Job(object):
    def __init__(self):
        self.id: uuid.UUID = uuid.uuid4()
        self.status = Status.REGISTERED


class Node(object):
    def __init__(self, name: str, id: str):
        self.name: str = name
        self.id: str = id
        self.status = Status.IDLE
        self.jobs: dict[uuid.UUID, Job] = dict()

    def get_job(self, id: uuid.UUID) -> Job | None:
        if id in self.jobs:
            return self.jobs[id]
        return None


class Pod(object):
    def __init__(self, name: str, id: int):
        self.name: str = name
        self.id: int = id
        self.nodes: dict[str, Node] = dict()

    def get_node(self, name: str) -> Node | None:
        if name in self.nodes:
            return self.nodes[name]
        return None

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
        self.queue: list[Job] = list()
        self.job_id: int = 0

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


cluster: Cluster = Cluster()


@app.route("/cloud/", methods=["POST"])
def init():
    """management: 1. cloud init"""
    if (cluster.get_pod("default")) != None:
        return jsonify(status=False, msg="cluster: already initialied")

    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu
        cluster.register_pod("default")
        # Let's wipe all containers at startup
        # TODO: do some filtering instead of wiping everything
        for container in dc.containers.list(all=True):
            dc.api.stop(container.id)
            dc.api.remove_container(container.id)
        return jsonify(status=True, msg="setup completed")

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
            container = dc.containers.create(
                image="ubuntu", name=f"{pod_name}_{node_name}"
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
        pass

    """management: 6. cloud launch PATH_TO_JOB"""
    if request.method == "POST":
        pass

    """management: 7. cloud abort JOB_ID"""
    if request.method == "DELETE":
        pass

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/log/", methods=["GET"])
def log() -> Response:
    """monitoring: 4. cloud job log JOB_ID"""
    """monitoring: 5. cloud log node NODE_ID"""
    if request.method == "GET":
        pass

    return jsonify(status=False, msg="cluster: what the hell is happenning")


if __name__ == "__main__":
    app.run(port=5551)
