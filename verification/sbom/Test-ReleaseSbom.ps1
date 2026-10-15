$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('octoship-sbom-' + [guid]::NewGuid().ToString('N'))
try {
    $payload = Join-Path $temporary 'payload'
    New-Item -ItemType Directory -Path $payload -Force | Out-Null
    $appBytes = [Text.Encoding]::UTF8.GetBytes('synthetic application payload')
    [IO.File]::WriteAllBytes((Join-Path $payload 'OctoShip.dll'), $appBytes)
    $deps = @{
        runtimeTarget = @{ name = '.NETCoreApp,Version=v10.0/win-x64'; signature = '' }
        targets = @{}
        libraries = @{
            'Fixture.Library/1.2.3' = @{ type = 'package'; serviceable = $true; sha512 = '' }
            'Fixture.Runtime/10.0.0' = @{ type = 'package'; serviceable = $true; sha512 = '' }
            'Fixture.Project/1.0.0' = @{ type = 'project'; serviceable = $false; sha512 = '' }
        }
    } | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText((Join-Path $payload 'OctoShip.deps.json'), $deps)
    $output = Join-Path $temporary 'sbom.json'
    & (Join-Path $root 'scripts/New-ReleaseSbom.ps1') -PayloadDirectory $payload -OutputPath $output -ApplicationName 'OctoShip for GitHub' -Version '1.6.1-preview.test'
    $bom = Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
    if ($bom.bomFormat -ne 'CycloneDX' -or $bom.specVersion -ne '1.5') { throw 'SBOM format/version is incorrect.' }
    $refs = @($bom.components | ForEach-Object { $_.'bom-ref' })
    if ($refs -notcontains 'pkg:nuget/Fixture.Library@1.2.3' -or $refs -notcontains 'pkg:nuget/Fixture.Runtime@10.0.0') { throw 'Resolved package dependencies are missing.' }
    if ($refs -contains 'pkg:nuget/Fixture.Project@1.0.0') { throw 'Project references must not be reported as package dependencies.' }
    $fileComponent = $bom.components | Where-Object { $_.type -eq 'file' -and $_.name -eq 'OctoShip.dll' }
    $expectedHash = (Get-FileHash -LiteralPath (Join-Path $payload 'OctoShip.dll') -Algorithm SHA256).Hash.ToLowerInvariant()
    if (!$fileComponent -or $fileComponent.hashes[0].alg -ne 'SHA-256' -or $fileComponent.hashes[0].content -ne $expectedHash) { throw 'Payload file hash is missing or incorrect.' }
    Write-Host 'Release SBOM fixture checks passed.'
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Recurse -Force }
}
