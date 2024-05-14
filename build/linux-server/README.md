## Build the Linux server binary version of the Crynux node

The binary version could be used on Linux servers with no GUI, or in a docker environment on the cloud.

### All in one script

```shell
# In the root folder of the project

$ ./build.sh
```

### Step by step

1. Prepare the project for packaging

Run the following command inside the root folder of the project:

```shell
# In the root folder of the project

$ ./build/linux-server/prepare.sh -w build/crynux_node
```

2. Create the distribution folder using pyinstaller

Go to the folder created in the last step, and run the package command:

```shell
# In the root folder of the project

$ cd build/crynux_node
$ ./package.ps1
```
