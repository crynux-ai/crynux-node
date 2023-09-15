# Crynux Node for the Hydrogen(H) Network

Crynux Node should be started on the machine with GPUs,
and will connect to the Crynux Network to execute training, fine-tuning and inference
tasks of the Stable Diffusion models for other applications.

## Run the node

1. Pull the Docker image from GitHub

```shell
# docker pull ghcr.io/crynux-ai/h-node:latest
```

2. Start the container

The port ```7412``` is exposed for the WebUI. And GPUs must be provided to the container.

```shell
# docker run -d -p 127.0.0.1:7412:7412 --gpus all ghcr.io/crynux-ai/h-node:latest
```


3. Visit the WebUI in the browser
```
http://localhost:7412
```

4. Follow the instructions in the WebUI to join the network.

## Build the Docker image from the source code

1. Clone the project

```shell
# git clone https://github.com/crynux-ai/h-node.git
```

2. Go to the root folder of the project

```shell
# cd h-node
```

3. Build the Docker image

```shell
# docker build -t h_node:dev -f .\build\Dockerfile . 
```

4. Start the container

```shell
# docker run -d -p 127.0.0.1:7412:7412 --gpus all h_node:dev
```
