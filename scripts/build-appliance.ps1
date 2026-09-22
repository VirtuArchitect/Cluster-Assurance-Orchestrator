param(
    [string]$Version = "0.1.0",
    [string]$ImageName = "cluster-assurance-orchestrator",
    [string]$OutputDir = "dist-appliance",
    [switch]$SkipDockerImage
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$outputRoot = Join-Path $repoRoot $OutputDir
$stagingRoot = Join-Path $outputRoot "cluster-assurance-orchestrator-$Version"
$imageTag = "$ImageName`:$Version"
$archivePath = Join-Path $outputRoot "cluster-assurance-orchestrator-$Version-appliance.zip"
$checksumPath = "$archivePath.sha256"

if (Test-Path $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingRoot "config") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingRoot "docs") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingRoot "scripts") | Out-Null

Copy-Item -LiteralPath (Join-Path $repoRoot "docker-compose.yml") -Destination $stagingRoot
Copy-Item -LiteralPath (Join-Path $repoRoot "config\appliance.env.example") -Destination (Join-Path $stagingRoot "config\appliance.env.example")
Copy-Item -LiteralPath (Join-Path $repoRoot "docs\appliance.md") -Destination (Join-Path $stagingRoot "docs\appliance.md")
Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") -Destination $stagingRoot

$manifest = [ordered]@{
    product = "Cluster Assurance Orchestrator for Nutanix Environments"
    version = $Version
    image = $imageTag
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    contents = @("docker-compose.yml", "config/appliance.env.example", "docs/appliance.md", "README.md")
    safety = "Read-only Prism collection; NCC and SSH execution disabled by default."
}

if (-not $SkipDockerImage) {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        Push-Location $repoRoot
        try {
            docker build --build-arg VITE_API_BASE="" -t $imageTag .
            $imageTar = Join-Path $stagingRoot "$ImageName-$Version-image.tar"
            docker save $imageTag -o $imageTar
            $manifest.contents += "$ImageName-$Version-image.tar"
            $manifest.image_tar = "$ImageName-$Version-image.tar"
        }
        finally {
            Pop-Location
        }
    }
    else {
        $manifest.image_tar = "not included; docker CLI not found"
    }
}
else {
    $manifest.image_tar = "not included; -SkipDockerImage was set"
}

($manifest | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath (Join-Path $stagingRoot "appliance-manifest.json") -Encoding UTF8

if (Test-Path $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archivePath -Force
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath
"$($hash.Hash)  $(Split-Path $archivePath -Leaf)" | Set-Content -LiteralPath $checksumPath -Encoding ASCII

Write-Host "Appliance bundle: $archivePath"
Write-Host "SHA256: $($hash.Hash)"
