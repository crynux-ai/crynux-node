# Crynux Node for the Hydrogen(H) Network

Start a Crynux Node to share the spared local GPU to others in exchange for tokens. Crynux Node will join the Crynux Network, receive the AI inference/training/fine-tuning tasks from the network, and execute them locally.

![Crynux Node WebUI](./docs/webui.png)

## Getting Started

A complete getting started guide to start a node is provided in the document:

[Join the Network](https://docs.crynux.ai/node-hosting/join-the-network)

## Run the node

1. Pull the Docker image from GitHub

```shell
# docker pull ghcr.io/crynux-ai/crynux-node:latest
```

2. Start the container

The port ```7412``` is exposed for the WebUI. And GPUs must be provided to the container.

```shell
# docker run -d -p 127.0.0.1:7412:7412 --gpus all ghcr.io/crynux-ai/crynux-node:latest
```


3. Visit the WebUI in the browser
```
http://localhost:7412
```

4. Follow the instructions in the WebUI to join the network.

## Build the Docker image from the source code

1. Clone the project

```shell
# git clone https://github.com/crynux-ai/crynux-node.git
```

2. Go to the root folder of the project

```shell
# cd crynux-node
```

3. Build the Docker image

```shell
# docker build -t crynux-node:dev -f .\build\Dockerfile . 
```

4. Start the container

```shell
# docker run -d -p 127.0.0.1:7412:7412 --gpus all crynux-node:dev
```

## Run tests

1. Clone the project

```shell
# git clone https://github.com/crynux-ai/crynux-node.git
```

2. Go to the root folder of the project

```shell
# cd crynux-node
```

3. Install the dependencies and package (preferably in a virtualenv)

```shell
# pip install -r requirements.txt && pip install .[test]
```

4. Run tests 

```shell
# pytest tests
```
