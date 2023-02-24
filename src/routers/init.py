from fastapi import APIRouter
from src.internal.type import Resp
from src.internal.cluster import cluster, dc
import shutil
import docker.errors


router = APIRouter(tags=["init"])


@router.post("/cloud/")
async def init() -> Resp:
    """management: 1. cloud init"""
    if cluster.initialized == True:
        return Resp(status=True, msg="cluster: warning already initialized")

    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu

        # TODO: do some filtering instead of wiping everything
        for container in dc.containers.list(all=True):
            dc.api.stop(container.id)
            dc.api.remove_container(container.id, force=True)

        try:
            shutil.rmtree("tmp")
        except OSError as e:
            print("tmp was already cleaned")

        cluster.initialized = True
        return Resp(status=True, msg="cluster: setup completed")

    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg="cluster: docker.errors.APIError")
