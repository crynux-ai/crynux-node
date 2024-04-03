## Build the Windows binary version of the Crynux node

### All in one script

```powershell
# In the root folder of the project

C:\PROJECT_ROOT> .\build\windows\build.ps1
```

### Step by step

1. Prepare the project for packaging

Run the following command inside the root folder of the project:

```powershell
C:\PROJECT_ROOT> .\build\windows\prepare.ps1 build\crynux_node
```

2. Create the distribution folder using pyinstaller

Go to the folder created in the last step, and run the package command:

```powershell
C:\PROJECT_ROOT> cd build\crynux_node
C:\PROJECT_ROOT\build\crynux_node> .\package.ps1
```
