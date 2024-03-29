import asyncio
import random
import string
from datetime import datetime

import httpx
import docker.errors

from src.utils.config import cluster, dc
from src.utils.calculate import calculate_cpu_percent
from src.utils.config import address


async def load_monitor():
    while True:
        await asyncio.sleep(0.5)
        if cluster.is_initialized():
            print("--------------------")
            print(f"{datetime.now()} - Load monitor is running")

            for pod in cluster.get_pods():
                total = 0
                usage = 0
                for server in pod.get_server_nodes():
                    if server.get_node_status() != "online":
                        continue
                    try:
                        container = dc.containers.get(server.get_node_id())
                        stats = container.stats(stream=False)  # type: ignore

                        cpu_usage: float = calculate_cpu_percent(
                            stats, pod.get_cpu_percent_cap()
                        )  # percentage
                        mem_usage: int = stats["memory_stats"]["usage"]  # bytes
                        network_in: int = stats["networks"]["eth0"]["rx_bytes"]
                        network_out: int = stats["networks"]["eth0"]["tx_bytes"]

                        server.set_cpu_usage(cpu_usage)
                        server.set_mem_usage(mem_usage)
                        server.set_network_in(network_in)
                        server.set_network_out(network_out)

                        total += 1
                        usage += cpu_usage
                    except docker.errors.APIError as e:
                        print(e)

                if total == 0:
                    print("No active server nodes found")
                    continue

                average = usage / total
                pod.set_usage(average)

                if not pod.get_is_elastic():
                    continue

                if average > pod.get_upper_threshold():
                    print(
                        f"Pod {pod.get_pod_id()} is experiencing high load, {average}%"
                    )
                    print("Trying to scale up...")
                    current_amount = len(pod.get_nodes())
                    if current_amount >= pod.get_max_nodes():
                        print("Cannot scale up, reached maximum pod node limit")
                        continue

                    async with httpx.AsyncClient(base_url=address["manager"]) as client:
                        resp = (
                            await client.post(
                                "/cloud/node/",
                                params={
                                    "node_type": "server",
                                    "pod_id": pod.get_pod_id(),
                                    "node_name": "auto-"
                                    + "".join(
                                        random.choices(
                                            string.ascii_letters + string.digits, k=8
                                        )
                                    ),
                                },
                                timeout=None,
                            )
                        ).json()
                        if resp["status"]:
                            print("Successful added a new server node")
                            resp = (
                                await client.post(
                                    "/cloud/server/launch/",
                                    params={
                                        "pod_id": pod.get_pod_id(),
                                    },
                                    timeout=None,
                                )
                            ).json()
                            if resp["status"]:
                                print("Successfully launched a new server node")
                            else:
                                print("Failed to launch a new server node")
                                print(resp["msg"])

                        else:
                            print("Failed to add a new server node")
                            print(resp["msg"])

                elif average < pod.get_lower_threshold():
                    print(
                        f"Pod {pod.get_pod_id()} is experiencing low load, {average}%"
                    )
                    print("Trying to scale down...")
                    current_amount = len(pod.get_server_nodes())
                    if current_amount <= pod.get_min_nodes():
                        print("Cannot scale down, reached minimum pod node limit")
                        continue

                    async with httpx.AsyncClient(base_url=address["manager"]) as client:
                        resp = (
                            await client.delete(
                                "/cloud/node/",
                                params={
                                    "node_id": pod.get_server_nodes()[-1].get_node_id()
                                },
                                timeout=None,
                            )
                        ).json()
                        if resp["status"]:
                            print("Scale down successful")
                        else:
                            print("Scale down failed")
                            print(resp["msg"])

                else:
                    print(
                        f"Pod {pod.get_pod_id()} is experiencing normal load, {average}%"
                    )
