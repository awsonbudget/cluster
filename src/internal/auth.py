from fastapi import HTTPException
from src.internal.cluster import cluster


async def verify_setup():
    if cluster.initialized == False:
        raise HTTPException(status_code=400, detail="cluster: please initialize first")
