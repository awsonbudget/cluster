# cluster

## Setup

Make sure you have [Poetry](https://python-poetry.org/docs/) installed locally on your machine and you can find `poetry` on your path.
You can double check by using `poetry --version`

Within this directory, use `poetry install` to install all dependencies.

Once that is done, use `poetry shell` to activate the environment.

In order to run the cluster, you need 1 command:

- To start the FastAPI server: `uvicorn src.main:app --reload --port 5001`

## McGill VM

- `uvicorn src.main:app --port 5001 --host 0.0.0.0`
