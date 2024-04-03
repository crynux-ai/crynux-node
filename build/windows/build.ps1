$PROJECT_ROOT = Get-Location
.\build\windows\prepare.ps1 build\crynux_node
Set-Location "build\crynux_node"
.\package.ps1
Set-Location $PROJECT_ROOT
