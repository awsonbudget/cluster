from fastapi import APIRouter, Depends
from src.utils.config import cluster, dc
from src.internal.auth import verify_setup
from src.internal.type import Resp
import docker.errors


router = APIRouter(tags=["server"])


@router.get("/cloud/server/", dependencies=[Depends(verify_setup)])
async def server_ls(pod_id: str) -> Resp:
    """cloud server ls POD_ID"""
    try:
        pod = cluster.get_pod_by_id(pod_id)
        servers = pod.get_server_nodes()
        for server in servers:
            try:
                container = dc.containers.get(server.get_node_id())
                print(container.stats(stream=False))  # type: ignore
            except docker.errors.APIError as e:
                print(e)
                return Resp(status=False, msg=f"cluster: docker.errors.APIError")

    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: pod {pod_id} ls failed: {e}")

    return Resp(status=True, msg="cluster: pod {pod_id} ls success")


@router.post("/cloud/server/launch/", dependencies=[Depends(verify_setup)])
async def server_launch(pod_id: str) -> Resp:
    """cloud server launch POD_ID"""
    try:
        pod = cluster.get_pod_by_id(pod_id)
        servers = pod.get_server_nodes()
        ports = []
        for server in servers:
            try:
                container = dc.containers.get(server.get_node_id())
                container.start()  # type: ignore
                ports.append(
                    dict(
                        node_id=server.get_node_id(),
                        port=server.get_port(),
                    )
                )
            except docker.errors.APIError as e:
                print(e)
                return Resp(status=False, msg=f"cluster: docker.errors.APIError")

            server.set_online()

    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: pod {pod_id} launch failed: {e}")

    return Resp(status=True, msg="cluster: pod {pod_id} launch success", data=ports)


@router.post("/cloud/server/resume/", dependencies=[Depends(verify_setup)])
async def server_resume(pod_id: str) -> Resp:
    """cloud server resume PDO_ID"""
    try:
        pod = cluster.get_pod_by_id(pod_id)
        servers = pod.get_server_nodes()
        ports = []
        for server in servers:
            try:
                container = dc.containers.get(server.get_node_id())
                container.start()  # type: ignore
                ports.append(
                    dict(
                        node_id=server.get_node_id(),
                        port=server.get_port(),
                    )
                )

            except docker.errors.APIError as e:
                print(e)
                return Resp(status=False, msg=f"cluster: docker.errors.APIError")

            server.set_online()

    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: pod {pod_id} resume failed: {e}")

    return Resp(status=True, msg="cluster: pod {pod_id} resume success", data=ports)


@router.post("/cloud/server/pause/", dependencies=[Depends(verify_setup)])
async def server_pause(pod_id: str) -> Resp:
    """cloud server launch POD_ID"""
    try:
        pod = cluster.get_pod_by_id(pod_id)
        servers = pod.get_server_nodes()
        ports = []
        for server in servers:
            try:
                container = dc.containers.get(server.get_node_id())
                container.stop(timeout=2)  # type: ignore
                ports.append(
                    dict(
                        node_id=server.get_node_id(),
                        port=server.get_port(),
                    )
                )

            except docker.errors.APIError as e:
                print(e)
                return Resp(status=False, msg=f"cluster: docker.errors.APIError")

            server.set_paused()

    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: pod {pod_id} pause failed: {e}")

    return Resp(status=True, msg="cluster: pod {pod_id} pause success", data=ports)
