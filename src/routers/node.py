from fastapi import APIRouter, Depends
from src.internal.type import Resp
from src.internal.cluster import cluster, dc, Node
from src.internal.auth import verify_setup
import os
import docker.errors


router = APIRouter(tags=["node"])


@router.get("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_ls(pod_id: str | None = None) -> Resp:
    """monitoring: 2. cloud node ls [RES_POD_ID]"""
    if pod_id == None:
        rtn = []
        for pod in cluster.get_pods():
            for node in pod.get_nodes():
                rtn.append(
                    dict(
                        node_name=node.get_node_name(),
                        node_id=node.get_node_id(),
                        node_status=node.get_node_status(),
                        pod_data=pod.toJSON(),
                    )
                )
        return Resp(status=True, data=rtn)

    pod = cluster.get_pod_by_id(pod_id)
    if pod == None:
        return Resp(status=False, msg=f"cluster: pod {pod_id} does not exist")

    rtn = []
    for node in pod.get_nodes():
        rtn.append(
            dict(
                node_name=node.get_node_name(),
                node_id=node.get_node_id(),
                node_status=node.get_node_status(),
                pod_data=pod.toJSON(),
            )
        )
    return Resp(status=True, data=rtn)


@router.post("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_register(node_name: str, pod_id: str) -> Resp:
    """management: 4. cloud register NODE_NAME [POD_ID]"""
    pod = cluster.get_pod_by_id(pod_id)
    if pod == None:
        return Resp(status=False, msg=f"cluster: pod with id {pod_id} does not exist")

    if cluster.has_dup_node_name(node_name, pod_id):
        return Resp(
            status=False,
            msg=f"cluster: node {node_name} already exist in pod with id {pod_id}",
        )

    try:
        container = dc.containers.run(
            image="ubuntu",
            name=f"{pod_id}_{node_name}",
            command=["tail", "-f", "/dev/null"],  # keep it running
            detach=True,
        )
        assert container.id != None  # type: ignore
        node = Node(node_name=node_name, node_id=container.id[0:12], pod_id=pod_id)  # type: ignore

        try:
            pod.add_node(node)
            cluster.add_node(node)
            cluster.add_available_node(node)
        except Exception as e:
            print(e)
            return Resp(status=False, msg=f"cluster: {e}")

        return Resp(
            status=True,
            msg=f"cluster: node {node_name} created in pod with id {pod.get_pod_id()}",
            data=node.get_node_id(),
        )

    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg=f"cluster: docker.errors.APIError")


@router.delete("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_rm(node_id: str) -> Resp:
    """management: 5. cloud rm NODE_ID"""
    try:
        node = cluster.get_node_by_id(node_id)
        pod = cluster.get_pod_by_id(node.get_pod_id())
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: {e}")

    try:
        dc.api.remove_container(container=node_id, force=True)

        try:
            pod.remove_node_by_id(node.get_node_id())
            cluster.remove_node_by_id(node_id)
            cluster.remove_available_node(node)
        except Exception as e:
            print(e)
            return Resp(status=False, msg=f"cluster: {e}")

        return Resp(
            status=True,
            msg=f"cluster: node {node.get_node_name()} removed in pod {node.get_pod_id()}",
        )
    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg=f"cluster: docker.errors.APIError")


@router.get("/cloud/node/log/", dependencies=[Depends(verify_setup)])
async def node_log(node_id: str) -> Resp:
    """monitoring: 5. cloud node log NODE_ID"""
    log = ""
    found = False
    for root, _, files in os.walk("tmp/" + node_id):
        for file in files:
            if file.endswith(".log"):
                with open(os.path.join(root, file), "r") as f:
                    log += "\n" + f.read()
                    found = True
    if not found:
        return Resp(
            status=False,
            msg=f"cluster: no log found for node {node_id}",
            data=f"no log found for node {node_id}",
        )
    return Resp(status=True, data=log)
