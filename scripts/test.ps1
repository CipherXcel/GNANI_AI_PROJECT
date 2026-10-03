$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
$command = Get-Command docker -ErrorAction SilentlyContinue
$dockerExe = if ($command) { $command.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
& $dockerExe compose -f docker-compose.yml up -d postgres
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed' }
& $dockerExe compose -f docker-compose.yml --profile test build test
if ($LASTEXITCODE -ne 0) { throw 'Test image build failed' }
& $dockerExe compose -f docker-compose.yml --profile test run --rm test
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
Set-Location -LiteralPath (Join-Path $root 'frontend')
npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
foreach ($check in @('typecheck', 'lint', 'build')) {
    npm.cmd run $check
    if ($LASTEXITCODE -ne 0) { throw "Frontend $check failed" }
}
Write-Output 'Backend and frontend checks passed. With the app running, run npm run test:ui from frontend for browser regression tests.'
