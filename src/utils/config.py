import json
from src.internal.cluster import Cluster
import docker

cluster: Cluster = Cluster()
dc = docker.from_env()

with open("config.json") as f:
    cluster_type = json.load(f)["cluster_type"]
    address = json.load(f)["address"]
