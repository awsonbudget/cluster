from __future__ import annotations
from src.internal.type import JobStatus, NodeStatus
from collections import deque
from dotenv import dotenv_values
import docker
import secrets
import string

dc = docker.from_env()
alphabet = string.ascii_letters.lower() + string.digits

"""
A couple notes on the cluster structure, especially the state:
There are 4 classes: Cluster, Pod, Node and Job.

Job
- a status state

Node
- a status state
- a list of jobs

Pod 
- a list of nodes

Cluster
- initialization status
- a map of pods indexed by pod_id for easy lookup
- a map of nodes indexed by node_id for easy lookup
- a list of currently running jobs
- a list of available nodes
"""


class Job(object):
    def __init__(
        self,
        job_id: str,
        job_name: str,
        node_id: str,
        job_status: JobStatus = JobStatus.RUNNING,
    ):
        self.__job_id: str = job_id
        self.__job_name: str = job_name
        self.__node_id: str = node_id
        self.__job_status: JobStatus = job_status

    def get_job_id(self) -> str:
        return self.__job_id

    def get_node_id(self) -> str:
        return self.__node_id

    def set_completed(self):
        self.__job_status = JobStatus.COMPLETED

    def set_aborted(self):
        self.__job_status = JobStatus.ABORTED

    def toJSON(self) -> dict:
        return {
            "job_id": self.__job_id,
            "job_name": self.__job_name,
            "node_id": self.__node_id,
            "job_status": self.__job_status,
        }


class Node(object):
    def __init__(self, node_name: str, node_id: str, pod_id: str):
        self.__node_id: str = node_id
        self.__node_name: str = node_name
        self.__pod_id: str = pod_id
        self.__node_status = NodeStatus.IDLE
        self.__jobs: dict[str, Job] = dict()  # key is the job id

    def get_node_id(self) -> str:
        return self.__node_id

    def get_node_name(self) -> str:
        return self.__node_name

    def get_pod_id(self) -> str:
        return self.__pod_id

    def get_node_status(self) -> NodeStatus:
        return self.__node_status

    def get_jobs(self) -> list[Job]:
        return list(self.__jobs.values())

    def set_running(self):
        self.__node_status = NodeStatus.RUNNING

    def set_idle(self):
        self.__node_status = NodeStatus.IDLE

    def add_job(self, job: Job):
        if job.get_job_id() in self.__jobs:
            raise Exception("job already exists")
        self.__jobs[job.get_job_id()] = job

    def toJSON(self) -> dict:
        return {
            "node_name": self.__node_name,
            "node_id": self.__node_id,
            "node_status": self.__node_status,
        }


class Pod(object):
    def __init__(self, pod_name: str):
        self.__pod_name: str = pod_name
        self.__pod_id: str = "".join(secrets.choice(alphabet) for _ in range(12))
        self.__nodes: dict[str, Node] = dict()  # key is the node id

    def get_pod_name(self) -> str:
        return self.__pod_name

    def get_pod_id(self) -> str:
        return self.__pod_id

    def get_node_by_id(self, node_id: str) -> Node:
        try:
            return self.__nodes[node_id]
        except KeyError:
            raise Exception("node does not exist")

    def get_nodes(self) -> list[Node]:
        return list(self.__nodes.values())

    def add_node(self, node: Node):
        if node.get_node_id() in self.__nodes:
            raise Exception("node already exists")
        self.__nodes[node.get_node_id()] = node

    def remove_node_by_id(self, node_id: str) -> Node:
        node = self.get_node_by_id(node_id)
        if node == None:
            raise Exception("node does not exist")
        if node.get_node_status() != NodeStatus.IDLE:
            raise Exception("node is not idle")
        try:
            return self.__nodes.pop(node_id)
        except KeyError:
            raise Exception("node does not exist")

    def toJSON(self) -> dict:
        return {"pod_name": self.__pod_name, "pod_id": self.__pod_id}


class Cluster(object):
    def __init__(self):
        self.__initialized: bool = False
        self.__pods: dict[str, Pod] = dict()  # key is the pod id
        self.__nodes: dict[str, Node] = dict()  # key is the node id
        self.__available_nodes: deque[Node] = deque()
        self.__running: dict[str, Job] = dict()  # key is the job id

    def is_initialized(self) -> bool:
        return self.__initialized

    def initialize(self):
        self.__initialized = True

    def has_dup_pod_name(self, pod_name: str) -> bool:
        for pod in self.get_pods():
            if pod.get_pod_name() == pod_name:
                return False
        return True

    def add_pod(self, pod: Pod):
        if pod.get_pod_id in self.__pods:
            raise Exception("pod id already exists")
        self.__pods[pod.get_pod_id()] = pod

    def get_pod_by_name(self, pod_name: str) -> Pod:
        for pod in self.get_pods():
            if pod.get_pod_name() == pod_name:
                return pod
        raise Exception(f"pod with name {pod_name} does not exist")

    def get_pod_by_id(self, pod_id: str) -> Pod:
        try:
            return self.__pods[pod_id]
        except KeyError:
            raise Exception(f"pod with id {pod_id} does not exist")

    def get_pods(self) -> list[Pod]:
        return list(self.__pods.values())

    def remove_pod_by_id(self, pod_id: str) -> Pod:
        try:
            return self.__pods.pop(pod_id)
        except KeyError:
            raise Exception(f"pod with id {pod_id} does not exist")

    def has_dup_node_name(self, node_name: str, pod_id: str) -> bool:
        pod = self.get_pod_by_id(pod_id)
        if pod == None:
            return False
        for node in pod.get_nodes():
            if node.get_node_name() == node_name:
                return False
        return True

    def add_node(self, node: Node):
        if node.get_node_id() in self.__nodes:
            raise Exception("node id already exists")
        self.__nodes[node.get_node_id()] = node

    def get_node_by_id(self, node_id: str) -> Node:
        try:
            return self.__nodes[node_id]
        except KeyError:
            raise Exception(f"node with id {node_id} does not exist")

    def remove_node_by_id(self, node_id: str) -> Node:
        node = self.get_node_by_id(node_id)
        if node == None:
            raise Exception("node does not exist")
        if node.get_node_status() != NodeStatus.IDLE:
            raise Exception("node is not idle")
        try:
            return self.__nodes.pop(node_id)
        except KeyError:
            raise Exception("node does not exist")

    def add_available_node(self, node: Node):
        self.__available_nodes.append(node)

    def has_available_nodes(self) -> bool:
        return (
            len(self.__available_nodes) > 0
            # the below should never be false, but just in case
            and self.__available_nodes[0].get_node_status() == NodeStatus.IDLE
        )

    def pop_available_node(self) -> Node:
        if not self.has_available_nodes():
            raise Exception("no available nodes")
        return self.__available_nodes.popleft()

    def remove_available_node(self, node: Node):
        self.__available_nodes.remove(node)

    def add_running_job(self, job: Job):
        if job.get_job_id() in self.__running:
            raise Exception("job id already exists")
        self.__running[job.get_job_id()] = job

    def remove_running(self, job_id: str) -> Job:
        try:
            return self.__running.pop(job_id)
        except KeyError:
            raise Exception(f"job with id {job_id} does not exist in the running list")

    def get_jobs(self) -> list[Job]:
        return list(self.__running.values())

    def get_jobs_under_node_id(self, node_id: str | None = None) -> list[Job]:
        rtn = []
        for pod in self.get_pods():
            for node in pod.get_nodes():
                if node_id:
                    if node.get_node_id() == node_id:
                        rtn.extend(node.get_jobs())
                else:
                    rtn.extend(node.get_jobs())
        return rtn


cluster: Cluster = Cluster()

config = dotenv_values(".env")
assert config["MANAGER"] != None
assert config["CLUSTER"] != None
