from fastapi import APIRouter, Depends
from src.internal.type import Resp
from src.internal.cluster import Pod, cluster
from src.internal.auth import verify_setup


router = APIRouter(tags=["pod"])


@router.get("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_ls():
    """monitoring: 1. cloud pod ls"""
    rtn = []
    for pod in cluster.get_pods():
        rtn.append(
            dict(
                pod_name=pod.get_pod_name(),
                pod_id=pod.get_pod_id(),
                total_nodes=len(pod.get_nodes()),
            )
        )
    return Resp(status=True, data=rtn)


@router.post("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_register(pod_name: str):
    """management: 2. cloud pod register POD_NAME"""
    # Pre condition check
    if cluster.has_dup_pod_name(pod_name):
        return Resp(status=False, msg=f"cluster: pod {pod_name} already exists")

    # Register pod
    pod = Pod(pod_name)
    try:
        cluster.add_pod(pod)
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: {e}")

    return Resp(
        status=True,
        msg=f"cluster: {pod_name} is added as a pod",
        data=pod.get_pod_id(),
    )


@router.delete("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_rm(pod_name: str):
    """management: 3. cloud pod rm POD_NAME"""
    # Pre condition check
    try:
        pod = cluster.get_pod_by_name(pod_name)
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: {e}")

    if len(pod.get_nodes()) > 0:
        return Resp(
            status=False,
            msg=f"cluster: failed to remove pod {pod_name} because it has nodes inside",
        )

    # Remove pod
    try:
        cluster.remove_pod_by_id(pod.get_pod_id())
    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: {e}")

    return Resp(status=True, msg=f"cluster: {pod_name} is removed from pods")
