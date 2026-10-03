param([switch]$Build)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
if (-not (Test-Path -LiteralPath '.env')) { throw 'Copy .env.example to .env and configure it first.' }
$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerExe = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
if (-not (Test-Path -LiteralPath $dockerExe)) { throw 'Install and start Docker Desktop first.' }
& $dockerExe info --format '{{.ServerVersion}}'
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with the Linux engine.' }
$composeArgs = @('compose', '-f', 'docker-compose.yml')
# Only profile-based local development mounts the normal host AWS credential chain.
$profileConfigured = Get-Content .env | Where-Object { $_ -match '^AWS_CONFIG_DIR=.+$' }
if ($env:AWS_CONFIG_DIR -or $profileConfigured) { $composeArgs += @('-f', 'docker-compose.aws-profile.yml') }
$composeArgs += @('up', '-d')
if ($Build) { $composeArgs += '--build' }
& $dockerExe @composeArgs
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Inspect docker compose logs; do not print .env.' }
$origin = ((Get-Content .env | Where-Object { $_ -match '^APP_ORIGIN=' }) -replace '^APP_ORIGIN=', '')
Write-Output "Suno: $origin. Processing continues after this terminal closes."
