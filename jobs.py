from celery import Celery
import requests
import docker
import docker.errors


app = Celery("jobs", broker="amqp://localhost")

dc = docker.from_env()


@app.task
def launch(job_id, node_id):
    with open(f"tmp/{job_id}.tar", "rb") as tar:
        container = dc.containers.get(node_id)
        container.put_archive("/", tar)
        # output = container.exec_run(["/bin/bash", "-c", "ls"])
        # print(output)
        # output = container.exec_run(["/bin/bash", "-c", "cd /tmp && ls"])
        # print(output)
        output = container.exec_run(["/bin/bash", "-c", f"chmod +x /tmp/{job_id}.sh"])
        print(output)
        output = container.exec_run(["/bin/bash", "-c", f"/tmp/{job_id}.sh"])
        print(output)
        requests.post(
            "http://localhost:5551/callback",
            params={
                "job_id": job_id,
                "exit_code": output.exit_code,
                "output": output.output.strip().decode("utf-8"),
            },
        )
    return
