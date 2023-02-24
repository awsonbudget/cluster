from __future__ import annotations
from src.internal.type import Status
from collections import deque
from typing import Optional
from dotenv import dotenv_values
import docker
import secrets
import string

dc = docker.from_env()
alphabet = string.ascii_letters.lower() + string.digits


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
    def __init__(self, name: str):
        self.name: str = name
        self.id: str = "".join(secrets.choice(alphabet) for _ in range(12))
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
        self.initialized: bool = False
        self.pods: dict[str, Pod] = dict()
        self.running: dict[str, Job] = dict()
        self.nodes: dict[str, Node] = dict()
        self.available: deque[Node] = deque()
        self.default_pod: Pod = Pod("default")
        self.pods[self.default_pod.id] = self.default_pod

    def pass_pod_name_check(self, name: str) -> bool:
        for pod in self.get_pods():
            if pod.name == name:
                return False
        return True

    def register_pod(self, name: str) -> bool:
        if not self.pass_pod_name_check(name):
            return False
        pod = Pod(name)
        self.pods[pod.id] = pod
        return True

    def get_pod_by_name(self, name: str) -> Pod | None:
        for pod in self.get_pods():
            if pod.name == name:
                return pod
        return None

    def get_pod_by_id(self, id: str) -> Pod | None:
        if id in self.pods.keys():
            return self.pods[id]
        return None

    def get_pods(self) -> list[Pod]:
        return list(self.pods.values())

    def remove_pod(self, name: str) -> Pod | None:
        pod = self.get_pod_by_name(name)
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


cluster: Cluster = Cluster()

config = dotenv_values(".env")
assert config["MANAGER"] != None
assert config["CLUSTER"] != None
