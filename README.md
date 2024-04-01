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


### Start the node from source code

#### Prepare the config file

Copy ```config/config.yml.shell_example``` to ```config/config.yml```. And adjust the file content according to your need:
```shell
# In the root folder of the project
$ cp config/config.yml.shell_example config/config.yml
```

#### Prepare the server venv

1. Create the venv in the root folder of the project:

```shell
# In the root folder of the project
$ python -m venv venv
```

2. Activate the venv and install the requirements:

```shell
# In the root folder of the project

# Use ./venv/Scripts/Activate.ps1 on Windows
$ ./venv/bin/activate

# Use requirements_macos.txt on Mac
(venv) $ pip install -r ./requirements_docker.txt
```

#### Prepare the worker venv

1. Get the source code of stable-diffusion-task and gpt-task using Git submodule:

```shell
# In the root folder of the project
$ git submodule update --init --recursive
```

2. Create a folder named "worker" under the root folder of the project, and copy ```src/crynux_worker_process.py``` to the folder:

```shell
# In the root folder of the project

$ mkdir worker
$ cp src/crynux_worker_process.py worker/
```
3. Create the venv under the worker folder:

```shell
# In the root folder of the project

$ cd worker
$ python -m venv venv
```

4. Activate the venv and install the requirements for stable-diffusion-task and gpt-task:

```shell
# In the worker folder

# Use ./venv/Scripts/Activate.ps1 on Windows
$ ./venv/bin/activate

# Use requirements_macos.txt on Mac
(venv) $ pip install -r ../stable-diffusion-task/requirements_cuda.txt

# Use requirements_macos.txt on Mac
(venv) $ pip install -r ../gpt-task/requirements_cuda.txt
```

#### Start the node

Activate the server's venv, and start from the ```src/app/main.py``` script:

```shell
# In the root folder of the project

# Use ./venv/Scripts/Activate.ps1 on Windows
$ ./venv/bin/activate

(venv) $ python src/app/main.py
```









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
