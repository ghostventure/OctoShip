param([Parameter(Mandatory = $true)][string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Run-Native([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" }
}

[xml]$project = Get-Content -LiteralPath FileToGitHub.csproj
$version = [string]$project.Project.PropertyGroup.Version
if ($version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') { throw 'Invalid Windows installer version.' }
$output = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $output -Force | Out-Null
$payload = Join-Path $output ('installer-payload-' + [guid]::NewGuid().ToString('N'))
$dotnet = $env:DOTNET_EXE
if (!$dotnet) {
    $dotnetCommand = Get-Command dotnet.exe -ErrorAction SilentlyContinue
    if ($dotnetCommand) { $dotnet = $dotnetCommand.Source }
}
if (!$dotnet) {
    foreach ($candidate in @((Join-Path $env:USERPROFILE '.dotnet\dotnet.exe'), (Join-Path $env:USERPROFILE '.dotnet10\dotnet.exe'))) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $dotnet = $candidate; break }
    }
}
if (!$dotnet -or !(Test-Path -LiteralPath $dotnet -PathType Leaf)) { throw 'The .NET SDK 10 dotnet.exe was not found. Set DOTNET_EXE to its full path.' }
Run-Native $dotnet @('publish', 'FileToGitHub.csproj', '-c', 'Release', '-r', 'win-x64', '--self-contained', 'false', '-p:DebugType=None', '-o', $payload)

$runtimeConfig = Get-Content -LiteralPath (Join-Path $payload 'OctoShip.runtimeconfig.json') -Raw | ConvertFrom-Json
if (!$runtimeConfig.runtimeOptions.frameworks -or $runtimeConfig.runtimeOptions.includedFrameworks) {
    throw 'Installer payload must be framework-dependent so Setup can install the .NET Desktop Runtime when needed.'
}

$iscc = $env:ISCC_EXE
if (!$iscc) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $iscc = $command.Source }
}
if (!$iscc) {
    foreach ($candidate in @(
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $iscc = $candidate; break }
    }
}
if (!$iscc -or !(Test-Path -LiteralPath $iscc -PathType Leaf)) { throw 'Inno Setup Compiler was not found. Set ISCC_EXE to its full path.' }

$installerName = "OctoShip-Setup-v$version-win-x64"
$scriptPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'installer\OctoShip.iss'
Run-Native $iscc @("/DPayloadDir=$payload", "/O$output", "/F$installerName", $scriptPath)
$installer = Join-Path $output "$installerName.exe"
if (!(Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'Inno Setup did not create the expected installer.' }
Write-Host "Runtime-bootstrapper installer: $installer"
