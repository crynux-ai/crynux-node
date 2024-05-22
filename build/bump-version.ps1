
param(
    [string]$VERSION
)

if (-not $VERSION) {
    Write-Error "Please set the version number in the argument"
    exit 1
}

Write-Output "Bumping version number to: $VERSION"

## Update pyproject.toml
(Get-Content "pyproject.toml") -replace "version = `"([0-9].[0-9].[0-9])`"", "version = `"$VERSION`"" | Set-Content "pyproject.toml"

## Update src/webui/package.json
(Get-Content "src/webui/package.json") -replace "`"version`": `"[0-9].[0-9].[0-9]`"", "`"version`": `"$VERSION`"" | Set-Content "src/webui/package.json"

## Update build/macos/crynux.spec
(Get-Content "build/macos/crynux.spec") -replace "'CFBundleShortVersionString': '[0-9].[0-9].[0-9]'", "'CFBundleShortVersionString': '$VERSION'" | Set-Content "build/macos/crynux.spec"

## Update build/macos/build.sh
(Get-Content "build/macos/build.sh") -replace "VERSION=[0-9].[0-9].[0-9]", "VERSION=$VERSION" | Set-Content "build/macos/build.sh"

## Update build/linux-server/package.sh
(Get-Content "build/linux-server/package.sh") -replace "VERSION=[0-9].[0-9].[0-9]", "VERSION=$VERSION" | Set-Content "build/linux-server/package.sh"

## Update build/windows/package.ps1
(Get-Content "build/windows/package.ps1") -replace "\`$VERSION = `"[0-9].[0-9].[0-9]`"", "`$VERSION = `"$VERSION`"" | Set-Content "build/windows/package.ps1"
