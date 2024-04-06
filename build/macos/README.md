## Build the Mac release package of the Crynux node

### All in one script

```shell
# In the root folder of the project

$ ./build/macos/build.sh
```

### Step by step

1. Prepare the project for packaging

Run the following command inside the root folder of the project:

```shell
$ ./build/macos/prepare.sh build/crynux_node
```

2. Create the distribution folder using pyinstaller

Go to the folder created in the last step, and run the package command:

```shell
$ cd build/crynux_node
$ ./package.sh
```
