from flask import Flask, jsonify
import docker

app = Flask(__name__)
app.debug = True

dc = docker.from_env()


@app.route("/")
def hello_world():
    containers = [c.short_id for c in dc.containers.list()]
    return jsonify(containers)


if __name__ == "__main__":
    app.run(port=5555)
