from flask import Flask, jsonify, request, Response
import docker
import docker.errors

app = Flask(__name__)
app.debug = True

dc = docker.from_env()


class Cloud(object):
    def __init__(self):
        # The outer dict has pod_name as the key
        # The inner dict has node_name as the key and node_id as the value
        self.pods: dict[str, dict[str, str]] = dict()
        # Technially we don't need these but it is a part of the requirement
        self.pod_id: int = 0
        self.pod_name_to_id: dict[str, int] = dict()

    def register_pod(self, name: str):
        self.pods[name] = dict()  # Init the "default" pod
        self.pod_name_to_id[name] = self.pod_id
        self.pod_id += 1


cloud: Cloud = Cloud()


@app.route("/cloud/", methods=["POST"])
def init():
    try:
        dc.images.pull("ubuntu")  # Assume all containers run on Ubuntu
        cloud.register_pod("default")

        return jsonify(status=True, msg="setup completed")
    except docker.errors.APIError as e:
        print(e)
        return jsonify(status=False, msg=f"cluster: docker.errors.APIError")


@app.route("/cloud/pod/", methods=["GET", "POST", "DELETE"])
def pod() -> Response:
    pod_name = request.args.get("pod_name")
    assert pod_name != None

    if request.method == "GET":
        rtn = []
        for k, v in cloud.pods.items():
            rtn.append([k, cloud.pod_name_to_id[k], len(v)])
        return jsonify(status=True, data=rtn)

    if request.method == "POST":
        if pod_name in cloud.pods:
            return jsonify(
                status=False, msg=f"cluster: {pod_name} is already a pod in pods"
            )

        cloud.register_pod(pod_name)
        return jsonify(status=True, msg=f"cluster: {pod_name} is added as a pod")

    if request.method == "DELETE":
        # TODO: check for instances before removing
        rtn = cloud.pods.pop(pod_name, False)
        if rtn == False:
            return jsonify(
                status=False, msg=f"cluster: {pod_name} is not a pod in pods"
            )
        return jsonify(status=True, msg=f"cluster: {pod_name} is removed from pods")

    return jsonify(status=False, msg="cluster: what the hell is happenning")


@app.route("/cloud/node/", methods=["POST", "DELETE"])
def node() -> Response:
    node_name = request.args.get("node_name")
    assert node_name != None
    pod_name = request.args.get("pod_name")
    if pod_name == None:
        pod_name = "default"

    if request.method == "POST":
        if not pod_name in cloud.pods:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")
        if node_name in cloud.pods[pod_name]:
            return jsonify(
                status=False,
                msg=f"cluster: node {node_name} already exist in pod {pod_name}",
            )

        try:
            container = dc.containers.create(
                image="ubuntu", name=f"{pod_name}_{node_name}"
            )
            assert container.id != None
            cloud.pods[pod_name][node_name] = container.id
            return jsonify(
                status=True,
                msg=f"cluster: node {node_name} created in pod {pod_name}",
            )
        except docker.errors.APIError as e:
            print(e)
            return jsonify(status=False, msg=f"cluster: docker.errors.APIError")

    if request.method == "DELETE":
        if not pod_name in cloud.pods:
            return jsonify(status=False, msg=f"cluster: pod {pod_name} does not exist")
        if not node_name in cloud.pods[pod_name]:
            return jsonify(
                status=False,
                msg=f"cluster: node {node_name} does not exist in pod {pod_name}",
            )

        try:
            dc.api.remove_container(container=cloud.pods[pod_name][node_name])
            cloud.pods[pod_name].pop(node_name)
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
