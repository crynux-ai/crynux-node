#!/bin/bash

while getopts ":s:u:p:t:" opt; do
  case $opt in
    s) IDENTITY="$OPTARG"
    ;;
    u) APPLE_USER="$OPTARG"
      ;;
    p) APPLE_PASS="$OPTARG"
      ;;
    t) APPLE_TEAM_ID="$OPTARG"
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
cd ./build/crynux_node || exit

if [ "$IDENTITY" ]; then
  echo "Packaging using identity: $IDENTITY"
  ./package.sh -s "$IDENTITY"
else
  echo "Packaging using local developer identity"
  ./package.sh
fi

if [ "$IDENTITY" ]; then
  ## Sign the DMG file
  echo "Signing the DMG file"
  codesign -s "$IDENTITY" "dist/Crynux Node.dmg"
fi

if [ "$IDENTITY" ]; then
  echo "Notarizing the DMG file"
  ## Sign the app and send it to apple for notarization
  python notarize.py \
    --package "dist/Crynux Node.dmg" \
    --username "$APPLE_USER" \
    --team "$APPLE_TEAM_ID" \
    --password "$APPLE_PASS"
fi
