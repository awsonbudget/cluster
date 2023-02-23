from celery import Celery
import requests
import docker
import docker.errors
import os

app = Celery("jobs", broker="amqp://localhost")

dc = docker.from_env()


@app.task
def launch(job_id, node_id, callback):
    folder = os.path.join("tmp", node_id)
    with open(os.path.join(folder, f"{job_id}.tar"), "rb") as tar:
        container = dc.containers.get(node_id)
        container.put_archive("/", tar)
        script = os.path.join(folder, f"{job_id}.sh")
        output = container.exec_run(["/bin/bash", "-c", f"chmod +x {script}"])
        print(output)
        output = container.exec_run(["/bin/bash", "-c", f"{script}"])
        print(output)
        requests.post(
            callback + "/internal/callback",
            params={
                "job_id": job_id,
                "node_id": node_id,
                "exit_code": output.exit_code,
                "output": output.output.strip().decode("utf-8"),
            },
        )
    return
