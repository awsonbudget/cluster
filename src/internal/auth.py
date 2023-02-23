from fastapi import HTTPException
from src.internal.cluster import cluster


async def verify_setup():
    if cluster.get_pod("default") == None:
        raise HTTPException(status_code=400, detail="cluster: please initialize first")
