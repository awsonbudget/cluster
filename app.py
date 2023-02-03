from flask import Flask, jsonify, request, Response
import docker
import docker.errors

app = Flask(__name__)
app.debug = True

dc = docker.from_env()

pods: dict = dict()


@app.route("/cloud/", methods=["POST"])
def init():
    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu
        pods["default"] = {}  # Init the "default" pod
        return jsonify(status=True, msg="setup completed")
    except docker.errors.APIError as e:
        print(e)
        return jsonify(status=False, msg=f"cluster: docker.errors.APIError")


@app.route("/cloud/pod/", methods=["POST", "DELETE"])
def pod() -> Response:
    pod_name = request.args.get("pod_name")

    if request.method == "POST":
        if pod_name in pods:
            return jsonify(
                status=False, msg=f"cluster: {pod_name} is already a pod in pods"
            )
        pods[pod_name] = {}
        return jsonify(status=True, msg=f"cluster: {pod_name} is added as a pod")

    if request.method == "DELETE":
        # TODO: check for instances before removing
        rtn = pods.pop(pod_name, False)
        if rtn == False:
            return jsonify(
                status=False, msg=f"cluster: {pod_name} is not a pod in pods"
            )
        return jsonify(status=True, msg=f"cluster: {pod_name} is removed from pods")

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/node/", methods=["POST", "DELETE"])
def node() -> Response:
    node_name = request.args.get("node_name")
    pod_name = request.args.get("pod_name")
    if not pod_name:
        pod_name = "default"

    if request.method == "POST":
        if not pod_name in pods:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")
        if node_name in pods[pod_name]:
            return jsonify(
                status=False,
                msg=f"cluster: node {node_name} already exist in pod {pod_name}",
            )

        try:
            container = dc.containers.create(
                image="ubuntu", name=f"{pod_name}_{node_name}"
            )
            pods[pod_name][node_name] = container.id
            return jsonify(
                status=True,
                msg=f"cluster: node {node_name} created in pod {pod_name}",
            )
        except docker.errors.APIError as e:
            print(e)
            return jsonify(status=False, msg=f"cluster: docker.errors.APIError")

    if request.method == "DELETE":
        if not pod_name in pods:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")
        if not node_name in pods[pod_name]:
            return jsonify(
                status=False,
                msg=f"cluster: node {node_name} does not exist in pod {pod_name}",
            )

        try:
            dc.api.remove_container(container=pods[pod_name][node_name])
            pods[pod_name].pop(node_name)
            return jsonify(
                status=True,
                msg=f"cluster: node {node_name} removed in pod {pod_name}",
            )
        except docker.errors.APIError as e:
            print(e)
            return jsonify(status=False, msg=f"cluster: docker.errors.APIError")

    return jsonify(status=False, msg="cluster: what the hell is happenning")


if __name__ == "__main__":
    app.run(port=5555)
