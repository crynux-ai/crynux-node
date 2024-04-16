#!/bin/bash

while getopts ":s:" opt; do
  case $opt in
    s) IDENTITY="$OPTARG"
    ;;
    \?) echo "Invalid option -$OPTARG" >&2
    exit 1
    ;;
  esac

  case $OPTARG in
    -*) echo "Option $opt needs a valid argument"
    exit 1
    ;;
  esac
done

## Prepare the dist project and install the environments
./build/macos/prepare.sh -w ./build/crynux_node

## Build the dist bundle
cd ./build/crynux_node
if [ $IDENTITY ]; then
  echo "Packaging using identity: $IDENTITY"
  ./package.sh -s $IDENTITY
else
  echo "Packaging using local developer identity"
  ./package.sh
fi

if [ $IDENTITY ]; then
  ## Sign the DMG file
  echo "Signing the DMG file"
  codesign -s $IDENTITY "dist/Crynux Node.dmg"
fi

## Sign the app and send it to apple for notarization
#cd dist
#python notarize.py \
#    --package "Crynux Node.dmg" \
#    --entitlements "../entitlements.plist" \
#    --primary-bundle-id ai.crynux.node \
#    --username $APPLE_USER \
#    --password $APPLE_PASS
