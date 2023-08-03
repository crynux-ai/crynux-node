## Crynux Node for the Hydrogen(H) Network

Crynux Node should be started on the machine with GPUs,
and will connect to the Crynux Network to execute training, fine-tuning and inference
tasks of Stable Diffusion models for other applications.

### Build the docker images
The docker images are built using Dockerfiles which are all located under the ```build``` folder.
The building commands, however, should be executed under the root folder of the project.

#### The server container

Build the server image:
   
```shell
$ docker build -t server:dev -f build/server.Dockerfile .
```


#### The worker container

Build the worker image:
   
```shell
$ docker build -t worker:dev -f build/worker.Dockerfile .
```

### Prepare the pretrained models

Download the popular pretrained models into ```build/data/pretrained-models```.
For example, download the Stable Diffusion 1.5 model, and place the ckpt file at:

```build/data/pretrained-models/stable-diffusion-v1-5-pruned/stable-diffusion-v1-5-pruned.ckpt```


### Start LoRA Runner using the docker images

#### Create the configuration files

The config files are located under ```/build/data```. Two files are required:
```/build/data/config.yml``` for the application and ```/build/data/gunicorn.conf.py```
for the Gunicorn http server.

We have provided two example config files under the folder. To run with the default config,
just rename the files, remove the trailing ```.example``` from the file names.

If you have customized requirements, such as serving under HTTPS protocol,
just modify the config files according to your needs.

#### Start the docker containers

All the related docker containers can be started easily
using docker compose:

```shell
$ cd build
$ docker compose up -d
```

Docker compose will start 3 containers: the server, the worker, and a redis instance.
The server and worker containers are started using the images we just built before.
The redis container is started using the official image.

After successfully startup, the server container will expose port ```5025``` to accept inbound requests.
