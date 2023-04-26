from fastapi import APIRouter, Depends
from src.utils.config import cluster, dc
from src.internal.auth import verify_setup
from src.internal.type import Resp
import docker.errors


router = APIRouter(tags=["server"])


@router.get("/cloud/server/", dependencies=[Depends(verify_setup)])
async def server_stat(pod_id: str, node_id: str | None = None) -> Resp:
    """cloud server stat POD_ID [NODE_ID]"""
    try:
        pod = cluster.get_pod_by_id(pod_id)
        servers = pod.get_server_nodes()
        data = {}
        for server in servers:
            if node_id != None and node_id != server.get_node_id():
                continue

            data[node_id] = (
                {
                    "cpu_usage": server.get_cpu_usage(),
                    "mem_usage": server.get_mem_usage(),
                    "network_in": server.get_network_in(),
                    "network_out": server.get_network_out(),
                },
            )

        return Resp(status=True, data=data)

    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: pod {pod_id} ls failed: {e}")


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
                print(container.status)  # type: ignore
                if container.status == "running":  # type: ignore
                    continue
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
            pod.set_cpu_percent_cap(
                min(cluster.get_cpu_limit(), cluster.get_cpu_available() / len(servers))
            )
            print(f"Launching {len(servers)} servers!")
            print(f"Config cap: {cluster.get_cpu_limit()}")
            print(f"Available cap: {cluster.get_cpu_available()/ len(servers)}")
            print(f"Final decision: {pod.get_cpu_percent_cap()}")

    except Exception as e:
        print(e)
        return Resp(status=False, msg=f"cluster: pod {pod_id} launch failed: {e}")

    return Resp(status=True, msg=f"cluster: pod {pod_id} launch success", data=ports)


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
                print(container.status)  # type: ignore
                if container.status == "running":  # type: ignore
                    continue
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
                print(container.status)  # type: ignore
                if container.status == "exited":  # type: ignore
                    continue
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
