from fastapi import APIRouter
from src.internal.type import Resp
from src.utils.config import cluster, dc, cluster_type

import shutil
import docker.errors


router = APIRouter(tags=["init"])


@router.post("/cloud/")
async def init(type: str) -> Resp:
    """management: 1. cloud init"""
    if cluster.is_initialized() == True:
        return Resp(status=True, msg="cluster: warning already initialized")

    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu
        dc.images.build(path="example/express", tag="aob-example-express:1.0")

        # TODO: do some filtering instead of wiping everything
        for container in dc.containers.list(all=True):
            dc.api.stop(container.id)
            dc.api.remove_container(container.id, force=True)

        try:
            shutil.rmtree("tmp")
        except OSError as e:
            print("tmp was already cleaned")

        cluster.initialize(
            type,
            cpu_limit=cluster_type[type]["cpu"],
            mem_limit=cluster_type[type]["mem"],
        )

        cluster.set_cpu_available(int(dc.info()["NCPU"]))
        print(f"Docker CPU available: {dc.info()['NCPU']}")
        return Resp(status=True, msg="cluster: setup completed")

    except docker.errors.APIError as e:
        print(e)
        return Resp(status=False, msg="cluster: docker.errors.APIError")
