from fastapi import APIRouter, Depends
from src.internal.type import Resp
from src.internal.cluster import cluster
from src.internal.auth import verify_setup
from src.internal.type import Resp


router = APIRouter(tags=["node"])

## List the pods
@router.get("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_ls():
    """monitoring: 1. cloud pod ls"""
    rtn = []
    for pod in cluster.get_pods():
        rtn.append(dict(name=pod.name, id=pod.id, nodes=len(pod.get_nodes())))
    return Resp(status=True, data=rtn)

## Register a new pod with pod name
@router.post("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_register(pod_name: str):
    """management: 2. cloud pod register POD_NAME"""
    status = cluster.register_pod(pod_name)
    if status == True:
        return Resp(status=True, msg=f"cluster: {pod_name} is added as a pod")
    else:
        return Resp(status=False, msg=f"cluster: pod {pod_name} already exists")


@router.delete("/cloud/pod/", dependencies=[Depends(verify_setup)])
async def pod_rm(pod_name: str):
    """management: 3. cloud pod rm POD_NAME"""
    if pod_name == "default":
        return Resp(status=False, msg=f"cluster: you cannot remove the default pod")
    #Remove the pod(not default)
    pod = cluster.remove_pod(pod_name)
    if pod:
        return Resp(status=True, msg=f"cluster: {pod_name} is removed from pods")
    else:
        return Resp(
            status=False,
            msg=f"cluster: failed to remove pod {pod_name} because it does not exist or it has nodes inside",
        )
