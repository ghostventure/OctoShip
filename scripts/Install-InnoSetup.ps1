$ErrorActionPreference = 'Stop'

$packageUrl = 'https://community.chocolatey.org/api/v2/package/innosetup/6.7.1'
$packageSha256 = 'A0DAD33DB33099D9CD2B89AC2D08B5D70C589B15118CED3B95F469F044F99950'
$installerSha256 = '4D11E8050B6185E0D49BD9E8CC661A7A59F44959A621D31D11033124C4E8A7B0'
$packageRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$workDirectory = Join-Path $packageRoot ('octoship-innosetup-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workDirectory -Force | Out-Null
$packagePath = Join-Path $workDirectory 'innosetup-6.7.1.nupkg'
$archivePath = Join-Path $workDirectory 'innosetup-6.7.1.zip'

Write-Host 'Downloading pinned Inno Setup 6.7.1 Chocolatey package.'
Invoke-WebRequest -Uri $packageUrl -OutFile $packagePath
$actualPackageHash = (Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash
if ($actualPackageHash -ne $packageSha256) {
    throw "Inno Setup package SHA-256 mismatch: expected $packageSha256, got $actualPackageHash."
}

$archivePath = Join-Path $workDirectory 'innosetup-6.7.1.zip'
Copy-Item -LiteralPath $packagePath -Destination $archivePath
$extractionDirectory = Join-Path $workDirectory 'package'
Expand-Archive -LiteralPath $archivePath -DestinationPath $extractionDirectory -Force
$installerPath = Join-Path $extractionDirectory 'tools\innosetup-6.7.1.exe'
if (!(Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw 'The pinned Chocolatey package did not contain tools/innosetup-6.7.1.exe.'
}
$actualInstallerHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash
if ($actualInstallerHash -ne $installerSha256) {
    throw "Inno Setup installer SHA-256 mismatch: expected $installerSha256, got $actualInstallerHash."
}

Write-Host 'Installing verified Inno Setup 6.7.1 silently.'
$install = Start-Process -FilePath $installerPath -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-' -Wait -PassThru -WindowStyle Hidden
if ($install.ExitCode -ne 0) {
    throw "Inno Setup installer exited with code $($install.ExitCode)."
}

$compilerCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
    (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (!$compiler) {
    throw 'Inno Setup installation completed, but ISCC.exe was not found in its expected install locations.'
}
$compilerInfo = Get-Item -LiteralPath $compiler
if ($compilerInfo.Length -le 0) { throw 'ISCC.exe exists but is empty.' }
Write-Host "Verified Inno Setup compiler: $compiler"
