import json
from src.internal.cluster import Cluster
import docker

cluster: Cluster = Cluster()
dc = docker.from_env()

with open("config.json") as f:
    config = json.load(f)
    cluster_type = config["cluster_type"]
    address = config["address"]
