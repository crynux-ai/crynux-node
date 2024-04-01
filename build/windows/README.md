## Build the Windows binary version of the Crynux node

1. Prepare the project for packaging

Run the following command inside the root folder of the project:

```powershell
$ .\build\windows\prepare.ps1 build\crynux_node
```

2. Create the distribution folder using pyinstaller

Go to the folder created in the last step, and run the package command:

```powershell
$ cd build\crynux_node
$ .\package.ps1
```
