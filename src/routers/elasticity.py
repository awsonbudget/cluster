import random
import string

from fastapi import APIRouter, Depends
import httpx
from src.internal.type import Resp
from src.routers.node import node_rm, node_register
from src.utils.config import cluster, cluster_type, address
from src.internal.auth import verify_setup


router = APIRouter(tags=["elasticity"])


@router.post("/cloud/elasticity/lower/", dependencies=[Depends(verify_setup)])
async def set_lower_threshold(pod_id: str, lower_threshold: int) -> Resp:
    cluster.get_pod_by_id(pod_id).set_lower_threshold(lower_threshold)
    return Resp(status=True)


@router.post("/cloud/elasticity/upper/", dependencies=[Depends(verify_setup)])
async def set_upper_threshold(pod_id: str, upper_threshold: int) -> Resp:
    cluster.get_pod_by_id(pod_id).set_upper_threshold(upper_threshold)
    return Resp(status=True)


@router.post("/cloud/elasticity/enable/", dependencies=[Depends(verify_setup)])
async def enable(pod_id: str, min_node: int, max_node: int) -> Resp:
    if (
        min_node > max_node
        or min_node < 1
        or max_node > cluster_type[cluster.get_type()]["node_limit"]
    ):
        return Resp(
            status=False,
            msg="Invalid node amount, the range must fit in [1, max specified in config]",
        )
    pod = cluster.get_pod_by_id(pod_id)
    pod.set_is_elastic(True)
    pod.set_max_nodes(max_node)
    pod.set_min_nodes(min_node)

    # Let's remove all job nodes in the pod
    for node in pod.get_nodes():
        if node.get_node_type() == "job":
            async with httpx.AsyncClient(base_url=address["manager"]) as client:
                resp = (
                    await client.delete(
                        "/cloud/node/",
                        params={s
                            "node_id": node.get_node_id(),
                        },
                    )
                ).json()
                if resp["status"] == False:
                    print(resp["msg"])

    while len(pod.get_server_nodes()) < min_node:
        async with httpx.AsyncClient(base_url=address["manager"]) as client:
            resp = (
                await client.post(
                    "/cloud/node/",
                    params={
                        "node_name": "auto-"
                        + "".join(
                            random.choices(string.ascii_letters + string.digits, k=8)
                        ).lower(),
                        "node_type": "server",
                        "pod_id": pod_id,
                    },
                )
            ).json()
            if resp["status"] == False:
                print(resp["msg"])

    while len(pod.get_server_nodes()) > max_node:
        async with httpx.AsyncClient(base_url=address["manager"]) as client:
            resp = (
                await client.delete(
                    "/cloud/node/",
                    params={
                        "node_id": pod.get_server_nodes()[-1].get_node_id(),
                    },
                )
            ).json()
            if resp["status"] == False:
                print(resp["msg"])

    return Resp(status=True)


@router.post("/cloud/elasticity/disable/", dependencies=[Depends(verify_setup)])
async def disable(pod_id: str) -> Resp:
    cluster.get_pod_by_id(pod_id).set_is_elastic(False)
    return Resp(status=True)
