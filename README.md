# Crynux Node for the Helium(He) Network

Start a Crynux Node to share the spared local GPU to others in exchange for tokens. Crynux Node will join the Crynux Network, receive the AI inference/training/fine-tuning tasks from the network, and execute them locally.

![Crynux Node WebUI](./docs/webui.png)

## Getting Started

A complete getting started guide to start a node is provided in the document:

[Join the Network](https://docs.crynux.ai/node-hosting/join-the-network)

## Start the node

### Start the node using Docker image
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

### Start the node on Mac
1. Download package
```shell
#TODO: host package on server
```

2. Unpack the package
```shell
WORKDIR=~/crynux_app && mkdir $WORKDIR && tar -xvzf crynux.tar.gz -C $WORKDIR && cd $WORKDIR
```

3. Start the node
```shell
# if you've loaded the model before:
bash start.sh run ~/crynux_data
# if you are brand new:
bash start.sh run
```

4. Visit the WebUI in the browser
```
http://localhost:7412
```

5. Follow the instructions in the WebUI to join the network.

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

## Build the package on Mac

1. Clone the project

```shell
# git clone https://github.com/crynux-ai/crynux-node.git
```

2. Go to the root folder of the project

```shell
# cd crynux-node
```

3. Generate runner environment and package the code

```shell
# bash build/macos/build.sh ~/crynux_app ~/crynux.tar.gz
```

4. Start the node

```shell
# bash start.sh run
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
# pip install -r requirements_docker.txt && pip install .[test]
```

4. Run tests 

```shell
# pytest tests
```
