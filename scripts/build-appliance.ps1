param(
    [string]$Version = "",
    [string]$ImageName = "cluster-assurance-orchestrator",
    [string]$OutputDir = "dist-appliance",
    [switch]$SkipDockerImage
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$release = Get-Content -LiteralPath (Join-Path $repoRoot "backend/app/release.json") -Raw | ConvertFrom-Json
if (-not $Version) { $Version = $release.version }
if ($Version -notmatch '^\d+\.\d+\.\d+(-rc\.\d+)?$') { throw "Invalid release version." }
if ($Version -cne $release.version) { throw "Bundle version must match backend/app/release.json." }
$revision = (git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Source revision is required." }
if (git -C $repoRoot status --porcelain) { throw "Release bundles require a clean checkout. Commit reviewed changes first." }
$builtAt = (Get-Date).ToUniversalTime().ToString("o")
$outputRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDir))
if (-not $outputRoot.StartsWith(([string]$repoRoot + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) { throw "Output must remain within the repository." }
$stagingRoot = Join-Path $outputRoot "cluster-assurance-orchestrator-$Version"
$imageTag = "$ImageName`:$Version"
$archivePath = Join-Path $outputRoot "cluster-assurance-orchestrator-$Version-appliance.zip"
$checksumPath = "$archivePath.sha256"

function Join-RepoPath {
    param([string[]]$Parts)

    $path = $repoRoot
    foreach ($part in $Parts) {
        $path = Join-Path $path $part
    }
    return $path
}

if (Test-Path $stagingRoot) { throw "Staging path already exists; choose a new output directory." }
New-Item -ItemType Directory -Path $stagingRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingRoot "config") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingRoot "docs") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingRoot "scripts") | Out-Null

$composeText = (Get-Content -LiteralPath (Join-RepoPath @("docker-compose.yml")) -Raw).Replace("cluster-assurance-orchestrator:local", $imageTag)
# Bundles run their exact saved image; they must not rebuild from missing source.
$composeText = $composeText -replace '(?ms)    build:\r?\n      context: \.\r?\n      args:\r?\n        VITE_API_BASE: ""\r?\n', ''
Set-Content -LiteralPath (Join-Path $stagingRoot "docker-compose.yml") -Value $composeText -Encoding utf8
Copy-Item -LiteralPath (Join-RepoPath @("config", "appliance.env.example")) -Destination (Join-Path (Join-Path $stagingRoot "config") "appliance.env.example")
Copy-Item -LiteralPath (Join-RepoPath @("docs", "appliance.md")) -Destination (Join-Path (Join-Path $stagingRoot "docs") "appliance.md")
Copy-Item -LiteralPath (Join-RepoPath @("README.md")) -Destination $stagingRoot
Copy-Item -LiteralPath (Join-RepoPath @("docs", "unattended-monitoring.md")) -Destination (Join-Path $stagingRoot "docs/unattended-monitoring.md")

$manifest = [ordered]@{
    product = "Cluster Assurance Orchestrator for Nutanix Environments"
    version = $Version
    revision = $revision
    source_state = "clean"
    channel = $release.channel
    production_approved = $false
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
            docker build --build-arg VITE_API_BASE="" --build-arg "CAO_BUILD_REVISION=$revision" --build-arg "CAO_BUILD_DATE=$builtAt" --build-arg "CAO_SOURCE_STATE=clean" -t $imageTag .
            if ($LASTEXITCODE -ne 0) { throw "Docker build failed." }
            $imageTar = Join-Path $stagingRoot "$ImageName-$Version-image.tar"
            docker save $imageTag -o $imageTar
            if ($LASTEXITCODE -ne 0) { throw "Docker save failed." }
            $manifest.image_id = (docker image inspect $imageTag --format "{{.Id}}")
            $manifest.image_tar_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $imageTar).Hash
            $manifest.contents += "$ImageName-$Version-image.tar"
            $manifest.image_tar = "$ImageName-$Version-image.tar"
        }
        finally {
            Pop-Location
        }
    }
    else { throw "Docker CLI is required unless -SkipDockerImage is explicit." }
}
else {
    $manifest.image_tar = "not included; -SkipDockerImage was set"
}

Copy-Item -LiteralPath (Join-RepoPath @("site", "documentation", "files")) -Destination (Join-Path $stagingRoot "docs/manuals") -Recurse
$manifest.contents += "docs/manuals"
$manifest.files = @(Get-ChildItem -LiteralPath $stagingRoot -File -Recurse | ForEach-Object {
    @{ path = [IO.Path]::GetRelativePath($stagingRoot, $_.FullName); sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
})
($manifest | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath (Join-Path $stagingRoot "appliance-manifest.json") -Encoding UTF8

if (Test-Path $archivePath) { throw "Release archive already exists; never overwrite a release." }
Compress-Archive -Path (Join-Path $stagingRoot "*") -DestinationPath $archivePath -Force
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath
"$($hash.Hash)  $(Split-Path $archivePath -Leaf)" | Set-Content -LiteralPath $checksumPath -Encoding ASCII

Write-Host "Appliance bundle: $archivePath"
Write-Host "SHA256: $($hash.Hash)"
