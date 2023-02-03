from flask import Flask, jsonify, request, Response
from typing import Optional
import docker

app = Flask(__name__)
app.debug = True

dc = docker.from_env()

pods: dict = dict()


@app.route("/")
def hello_world():
    containers = [c.short_id for c in dc.containers.list()]
    return jsonify(containers)


@app.route("/cloud/pod/<string:name>", methods=["POST", "DELETE"])
def pod(name: Optional[str] = None) -> Response:
    if request.method == "POST":
        if name in pods:
            return jsonify(
                status=False, msg=f"cluster: {name} is already a pod in pods"
            )
        pods[name] = []
        return jsonify(status=True, msg=f"cluster: {name} is added as a pod")

    if request.method == "DELETE":
        # TODO: check for instances before removing
        rtn = pods.pop(name, False)

        if rtn == False:
            return jsonify(status=False, msg=f"cluster: {name} is not a pod in pods")
        return jsonify(status=True, msg=f"cluster: {name} is removed from pods")

    return jsonify(status=False, msg="cluster: what the hell is happenning")


if __name__ == "__main__":
    app.run(port=5555)
