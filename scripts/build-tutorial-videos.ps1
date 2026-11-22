param()
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot
try {
    python scripts/build-tutorial-frames.py
    if ($LASTEXITCODE -ne 0) { throw 'Tutorial slide generation failed.' }
    $framesPath = (Resolve-Path 'tmp/tutorial-frames').Path
    $mediaPath = [IO.Path]::GetFullPath((Join-Path $repoRoot 'site/tutorials/media'))
    New-Item -ItemType Directory -Force -Path $mediaPath | Out-Null
    # Disposable authoring container only; no application dependency or live endpoint.
    docker run --rm --mount "type=bind,source=$framesPath,target=/frames,readonly" --mount "type=bind,source=$mediaPath,target=/output" python:3.12-slim sh -c 'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ffmpeg >/dev/null && for d in /frames/*; do ffmpeg -hide_banner -loglevel error -y -framerate 1/10 -i "$d/%02d.png" -c:v libx264 -preset fast -crf 24 -pix_fmt yuv420p -r 24 -movflags +faststart "/output/$(basename "$d").mp4"; done'
    if ($LASTEXITCODE -ne 0) { throw 'Tutorial encoding failed.' }
    python scripts/catalogue-tutorial-media.py
    if ($LASTEXITCODE -ne 0) { throw 'Tutorial media validation failed.' }
}
finally { Pop-Location }
