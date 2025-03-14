#! /bin/bash

# Check if blockchain argument is provided
if [ $# -eq 0 ]; then
    echo "Error: No blockchain argument provided"
    echo "Usage: $0 <blockchain>"
    exit 1
fi

# Get the blockchain argument
blockchain=$1

# Define an array of file pairs with names
# Format: "name|source_path|destination_path"
declare -a file_pairs=(
    "WebUI|./src/webui/src/config.${blockchain}.js|./src/webui/src/config.js"
    "Node Docker|./build/docker/config.yml.${blockchain}|./build/docker/config.yml.example"
)

# Process each file pair
for pair in "${file_pairs[@]}"; do
    # Split the pair into name, source, and destination
    IFS="|" read -r name source_file destination_file <<< "$pair"

    echo "Processing configuration for: $name"

    # Check if source file exists
    if [ ! -f "$source_file" ]; then
        echo "Error: Source file $source_file does not exist"
        continue
    fi

    # Copy the file
    echo "Copying $source_file to $destination_file"
    cp "$source_file" "$destination_file"

    if [ $? -eq 0 ]; then
        echo "Configuration file for $name successfully updated for $blockchain"
    else
        echo "Error: Failed to copy configuration file for $name"
    fi

    echo ""
done

echo "Configuration update completed."
