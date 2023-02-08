from celery import Celery
import requests
import docker
import docker.errors

import time

app = Celery("jobs", broker="amqp://localhost")


@app.task
def launch(job_id):
    time.sleep(15)
    requests.post("http://localhost:5551/cloud/callback", params={"job_id": job_id})
    return
