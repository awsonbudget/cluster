from __future__ import annotations
from fastapi import FastAPI, Request
import time
from src.routers import init, internal, job, server, node, pod

app = FastAPI()


@app.get("/ping/")
async def ping() -> str:
    return "pong"


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


app.include_router(init.router)
app.include_router(pod.router)
app.include_router(node.router)
app.include_router(job.router)
app.include_router(server.router)
app.include_router(internal.router)
