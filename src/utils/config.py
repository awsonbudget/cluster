import json
import docker


from src.internal.cluster import Cluster

cluster: Cluster = Cluster()
dc = docker.from_env()

with open("config.json") as f:
    config = json.load(f)
    cluster_type = config["cluster_type"]
    address = config["address"]
