#!/bin/bash

echo "Bumping version number to: $1"

sed -i -E "s/version = \"[0-9].[0-9].[0-9]\"/version = \"$1\"/g" pyproject.toml
sed -i -E "s/\"version\": \"[0-9].[0-9].[0-9]\"/\"version\": \"$1\"/g" src/webui/package.json
sed -i -E "s/'CFBundleShortVersionString': '[0-9].[0-9].[0-9]'/'CFBundleShortVersionString': '$1'/g" build/macos/crynux.spec
sed -i -E "s/VERSION=[0-9].[0-9].[0-9]/VERSION=$1/g" build/macos/build.sh
sed -i -E "s/VERSION=[0-9].[0-9].[0-9]/VERSION=$1/g" build/linux-server/package.sh
sed -i -E "s/\$VERSION = \"[0-9].[0-9].[0-9]\"/\$VERSION = \"$1\"/g" build/windows/package.ps1
sed -i -E "s/RELEASE_VERSION: [0-9].[0-9].[0-9]/RELEASE_VERSION: $1/g" .github/workflows/release-all.yml

