# Check if blockchain argument is provided
if ($args.Count -eq 0) {
    Write-Host "Error: No blockchain argument provided" -ForegroundColor Red
    Write-Host "Usage: .\set-config-files.ps1 <blockchain>"
    exit 1
}

# Get the blockchain argument
$blockchain = $args[0]

# Define an array of file pairs with names
# Format: @("name", "source_path", "destination_path")
$file_pairs = @(
    @("WebUI", ".\src\webui\src\config.${blockchain}.js", ".\src\webui\src\config.js"),
    @("Node Docker", ".\build\docker\config.yml.${blockchain}", ".\build\docker\config.yml.example"),
    @("Node MacOS", ".\build\macos\config.yml.${blockchain}", ".\build\macos\config.yml.example"),
    @("Node Windows", ".\build\windows\config.yml.${blockchain}", ".\build\windows\config.yml.example")
)

# Process each file pair
foreach ($pair in $file_pairs) {
    $name = $pair[0]
    $source_file = $pair[1]
    $destination_file = $pair[2]

    Write-Host "Processing configuration for: $name"

    # Check if source file exists
    if (-not (Test-Path $source_file)) {
        Write-Host "Error: Source file $source_file does not exist" -ForegroundColor Red
        continue
    }

    # Copy the file
    Write-Host "Copying $source_file to $destination_file"
    try {
        Copy-Item -Path $source_file -Destination $destination_file -Force
        Write-Host "Configuration file for $name successfully updated for $blockchain" -ForegroundColor Green
    }
    catch {
        Write-Host "Error: Failed to copy configuration file for $name" -ForegroundColor Red
        Write-Host $_.Exception.Message
    }

    Write-Host ""
}

Write-Host "Configuration update completed." -ForegroundColor Cyan
