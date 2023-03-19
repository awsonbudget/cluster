from fastapi import HTTPException
from src.utils.config import cluster


async def verify_setup():
    if cluster.is_initialized() == False:
        raise HTTPException(status_code=400, detail="cluster: please initialize first")
