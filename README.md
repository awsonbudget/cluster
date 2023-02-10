# cluster

## Setup

Make sure you have [Poetry](https://python-poetry.org/docs/) installed locally on your machine and you can find `poetry` on your path.
You can double check by using `poetry --version`

Within this directory, use `poetry install` to install all dependencies.

Once that is done, use `poetry shell` to activate the environment.

Before we launch the project, we also need to make sure [RabbitMQ](https://www.rabbitmq.com/download.html) is installed locally as well. We use RabbitMQ as our message queue.

On Debiand-based systems, start a RabbitMQ server with `systemctl start rabbitmq-server`

On MacOS, you can use `brew install rabbitmq` and `brew service start rabbitmq`

In order to run the cluster, you need 2 commands:

- To start the Flask server: `python3 app.py`
- To start the Celery worker: `celery -A jobs worker --loglevel=INFO`
