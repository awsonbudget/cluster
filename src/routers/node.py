from fastapi import APIRouter, Depends
from src.internal.type import Resp
from src.internal.cluster import cluster, dc, Node
from src.internal.auth import verify_setup
from src.internal.type import Resp
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
                        name=node.name,
                        id=node.id,
                        status=node.status,
                        pod=pod.toJSON(),
                    )
                )
        return Resp(status=True, data=rtn)

    pod = cluster.get_pod_by_id(pod_id)
    if pod == None:
        return Resp(status=False, msg=f"cluster: pod {pod_id} does not exist")

    rtn = []
    for node in pod.get_nodes():
        rtn.append(
            dict(name=node.name, id=node.id, status=node.status, pod=pod.toJSON())
        )
    return Resp(status=True, data=rtn)


@router.post("/cloud/node/", dependencies=[Depends(verify_setup)])
async def node_register(node_name: str, pod_id: str | None = None) -> Resp:
    """management: 4. cloud register NODE_NAME [POD_ID]"""
    pod = None
    if pod_id == None:
        pod = cluster.default_pod
    else:
        pod = cluster.get_pod_by_id(pod_id)
    if pod == None:
        return Resp(status=False, msg=f"cluster: pod with id {pod_id} does not exist")

    if pod.get_node(node_name) != None:
        return Resp(
            status=False,
            msg=f"cluster: node {node_name} already exist in pod with id {pod_id}",
        )

    try:
        container = dc.containers.run(
            image="ubuntu",
            name=f"{pod.id}_{node_name}",
            command=["tail", "-f", "/dev/null"],  # keep it running
            detach=True,
        )
        assert container.id != None
        node = Node(name=node_name, id=container.id[0:12])
        status = pod.add_node(node)
        cluster.nodes[node.id] = node
        cluster.available.append(node)
        if status:
            return Resp(
                status=True,
                msg=f"cluster: node {node_name} created in pod with id {pod.id}",
            )
        else:
            return Resp(
                status=False,
                msg=f"cluster: node {node_name} already exist in pod with id {pod.id}",
            )

    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg=f"cluster: docker.errors.APIError")


@router.delete("/cloud/node/", dependencies=[Depends(verify_setup)])
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
            status=False, msg=f"cluster: no log found for node {node_id}", data="empty"
        )
    return Resp(status=True, data=log)
