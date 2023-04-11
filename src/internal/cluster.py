from __future__ import annotations
from typing import Literal
from collections import deque
import secrets
import string

from src.internal.type import JobStatus, JobNodeStatus, ServerNodeStatus

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
    def __init__(
        self,
        node_name: str,
        node_id: str,
        pod_id: str,
        node_type: Literal["job", "server"],
    ):
        self.__node_id: str = node_id
        self.__node_name: str = node_name
        self.__pod_id: str = pod_id
        self.__node_type: Literal["job", "server"] = node_type

    def get_node_id(self) -> str:
        return self.__node_id

    def get_node_name(self) -> str:
        return self.__node_name

    def get_pod_id(self) -> str:
        return self.__pod_id

    def get_node_type(self) -> Literal["job", "server"]:
        return self.__node_type


class JobNode(Node):
    def __init__(self, node_name: str, node_id: str, pod_id: str):
        super().__init__(node_name, node_id, pod_id, "job")
        self.__node_status: JobNodeStatus = JobNodeStatus.IDLE
        self.__jobs: dict[str, Job] = dict()  # key is the job id

    def get_node_status(self) -> JobNodeStatus:
        return self.__node_status

    def set_running(self):
        self.__node_status = JobNodeStatus.RUNNING

    def set_idle(self):
        self.__node_status = JobNodeStatus.IDLE

    def get_jobs(self) -> list[Job]:
        return list(self.__jobs.values())

    def add_job(self, job: Job):
        if job.get_job_id() in self.__jobs:
            raise Exception("job already exists")
        self.__jobs[job.get_job_id()] = job

    def toJSON(self) -> dict:
        return {
            "node_name": self.get_node_name(),
            "node_id": self.get_node_id(),
            "node_status": self.get_node_status(),
        }


class ServerNode(Node):
    def __init__(self, node_name: str, node_id: str, pod_id: str, port: int):
        super().__init__(node_name, node_id, pod_id, "server")
        self.__node_status: ServerNodeStatus = ServerNodeStatus.NEW
        self.__port: int = port
        self.__cpu_usage: float = 0.0
        self.__mem_usage: int = 0
        self.__network_in: int = 0
        self.__network_out: int = 0

    def get_cpu_usage(self) -> float:
        return self.__cpu_usage

    def get_mem_usage(self) -> int:
        return self.__mem_usage

    def get_network_in(self) -> int:
        return self.__network_in

    def get_network_out(self) -> int:
        return self.__network_out

    def set_cpu_usage(self, cpu_usage: float):
        self.__cpu_usage = cpu_usage

    def set_mem_usage(self, mem_usage: int):
        self.__mem_usage = mem_usage

    def set_network_in(self, network_in: int):
        self.__network_in = network_in

    def set_network_out(self, network_out: int):
        self.__network_out = network_out

    def get_node_status(self) -> ServerNodeStatus:
        return self.__node_status

    def set_online(self):
        self.__node_status = ServerNodeStatus.ONLINE

    def set_paused(self):
        self.__node_status = ServerNodeStatus.PAUSED

    def get_port(self) -> int:
        if self.__port is None:
            raise Exception("server node port is not set somehow")
        return self.__port

    def toJSON(self) -> dict:
        return {
            "node_name": self.get_node_name(),
            "node_id": self.get_node_id(),
            "node_status": self.get_node_status(),
            "port": self.get_port(),
        }


class Pod(object):
    def __init__(self, pod_name: str):
        self.__pod_name: str = pod_name
        self.__pod_id: str = "".join(secrets.choice(alphabet) for _ in range(12))
        self.__nodes: dict[str, ServerNode | JobNode] = dict()  # key is the node id
        self.__cpu_percent_cap: float
        self.__is_elastic: bool = False
        self.__usage: float = 0.0
        self.__lower_threshold: int = 20
        self.__upper_threshold: int = 80
        self.__min_nodes: int = 0
        self.__max_nodes: int = 0

    def get_pod_name(self) -> str:
        return self.__pod_name

    def get_pod_id(self) -> str:
        return self.__pod_id

    def get_node_by_id(self, node_id: str) -> ServerNode | JobNode:
        try:
            return self.__nodes[node_id]
        except KeyError:
            raise Exception("node does not exist")

    def get_nodes(self) -> list[JobNode | ServerNode]:
        return list(self.__nodes.values())

    def get_server_nodes(self) -> list[ServerNode]:
        return [node for node in self.__nodes.values() if isinstance(node, ServerNode)]

    def add_node(self, node: ServerNode | JobNode):
        if node.get_node_id() in self.__nodes:
            raise Exception("node already exists")
        self.__nodes[node.get_node_id()] = node

    def remove_node_by_id(self, node_id: str) -> JobNode | ServerNode:
        node = self.get_node_by_id(node_id)
        if node == None:
            raise Exception("node does not exist")
        if isinstance(node, JobNode) and node.get_node_status() != JobNodeStatus.IDLE:
            raise Exception("job node is not idle")
        try:
            return self.__nodes.pop(node_id)
        except KeyError:
            raise Exception("node does not exist")

    def set_cpu_percent_cap(self, cpu_percent_cap: float):
        self.__cpu_percent_cap = cpu_percent_cap

    def get_cpu_percent_cap(self) -> float:
        return self.__cpu_percent_cap

    def set_is_elastic(self, is_elastic: bool):
        self.__is_elastic = is_elastic

    def get_is_elastic(self) -> bool:
        return self.__is_elastic

    def set_min_nodes(self, min_nodes: int):
        self.__min_nodes = min_nodes

    def get_min_nodes(self) -> int:
        return self.__min_nodes

    def set_max_nodes(self, max_nodes: int):
        self.__max_nodes = max_nodes

    def get_max_nodes(self) -> int:
        return self.__max_nodes

    def get_lower_threshold(self) -> int:
        return self.__lower_threshold

    def get_upper_threshold(self) -> int:
        return self.__upper_threshold

    def set_lower_threshold(self, lower_threshold: int):
        self.__lower_threshold = lower_threshold

    def set_upper_threshold(self, upper_threshold: int):
        self.__upper_threshold = upper_threshold

    def get_usage(self) -> float:
        return self.__usage

    def set_usage(self, usage: float):
        self.__usage = usage

    def toJSON(self) -> dict:
        return {"pod_name": self.__pod_name, "pod_id": self.__pod_id}


class Cluster(object):
    def __init__(self):
        self.__initialized: bool = False
        self.__type: str
        self.__pods: dict[str, Pod] = dict()  # key is the pod id
        self.__nodes: dict[str, JobNode | ServerNode] = dict()  # key is the node id
        self.__available_job_nodes: deque[JobNode] = deque()
        self.__running_job: dict[str, Job] = dict()  # key is the job id
        self.__available_port: int = 9999
        self.__cpu_limit: float
        self.__mem_limit: int
        self.__cpu_available: int

    def is_initialized(self) -> bool:
        return self.__initialized

    def initialize(self, type: str, cpu_limit: float, mem_limit: int):
        self.__type = type
        self.__cpu_limit = cpu_limit
        self.__mem_limit = mem_limit
        self.__initialized = True

    def get_type(self) -> str:
        return self.__type

    def get_cpu_limit(self) -> float:
        return self.__cpu_limit

    def get_mem_limit(self) -> int:
        return self.__mem_limit

    def has_dup_pod_name(self, pod_name: str) -> bool:
        for pod in self.get_pods():
            if pod.get_pod_name() == pod_name:
                return True
        return False

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
        for node in pod.get_nodes():
            if node.get_node_name() == node_name:
                return True
        return False

    def add_node(self, node: JobNode | ServerNode):
        if node.get_node_id() in self.__nodes:
            raise Exception("node id already exists")
        self.__nodes[node.get_node_id()] = node

    def get_node_by_id(self, node_id: str) -> JobNode | ServerNode:
        try:
            return self.__nodes[node_id]
        except KeyError:
            raise Exception(f"node with id {node_id} does not exist")

    def remove_node_by_id(self, node_id: str) -> JobNode | ServerNode:
        node = self.get_node_by_id(node_id)
        if node == None:
            raise Exception("node does not exist")
        if isinstance(node, JobNode) and node.get_node_status() != JobNodeStatus.IDLE:
            raise Exception("job node is not idle")
        try:
            return self.__nodes.pop(node_id)
        except KeyError:
            raise Exception("node does not exist")

    def add_available_job_node(self, node: JobNode):
        self.__available_job_nodes.append(node)

    def has_available_job_nodes(self) -> bool:
        return (
            len(self.__available_job_nodes) > 0
            # the below should never be false, but just in case
            and self.__available_job_nodes[0].get_node_status() == JobNodeStatus.IDLE
        )

    def pop_available_job_node(self) -> JobNode:
        if not self.has_available_job_nodes():
            raise Exception("no available nodes")
        return self.__available_job_nodes.popleft()

    def remove_available_job_node(self, node: JobNode):
        self.__available_job_nodes.remove(node)

    def add_running_job(self, job: Job):
        if job.get_job_id() in self.__running_job:
            raise Exception("job id already exists")
        self.__running_job[job.get_job_id()] = job

    def remove_running_job(self, job_id: str) -> Job:
        try:
            return self.__running_job.pop(job_id)
        except KeyError:
            raise Exception(f"job with id {job_id} does not exist in the running list")

    def get_jobs_under_node_id(self, node_id: str | None = None) -> list[Job]:
        rtn = []
        for pod in self.get_pods():
            for node in pod.get_nodes():
                if isinstance(node, JobNode):
                    if node_id:
                        if node.get_node_id() == node_id:
                            rtn.extend(node.get_jobs())
                    else:
                        rtn.extend(node.get_jobs())
        return rtn

    def get_available_port(self) -> int:
        self.__available_port += 1
        return self.__available_port

    def set_cpu_available(self, cpu_available: int):
        self.__cpu_available = cpu_available

    def get_cpu_available(self) -> int:
        return self.__cpu_available
