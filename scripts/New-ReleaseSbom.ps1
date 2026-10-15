param(
    [Parameter(Mandatory = $true)][string]$PayloadDirectory,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(Mandatory = $true)][string]$ApplicationName,
    [Parameter(Mandatory = $true)][string]$Version
)
$ErrorActionPreference = 'Stop'

$payload = (Resolve-Path -LiteralPath $PayloadDirectory).Path
$payloadUri = [Uri]::new($payload.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar)
$files = @(Get-ChildItem -LiteralPath $payload -File -Recurse | Sort-Object FullName)
if ($files.Count -eq 0) { throw 'Cannot generate an SBOM for an empty payload.' }
$depsFiles = @($files | Where-Object Name -Like '*.deps.json')
if ($depsFiles.Count -ne 1) { throw "Expected exactly one .deps.json in the payload; found $($depsFiles.Count)." }
$deps = Get-Content -LiteralPath $depsFiles[0].FullName -Raw | ConvertFrom-Json
$components = [System.Collections.Generic.List[object]]::new()
$components.Add(@{
    type = 'application'; name = $ApplicationName; version = $Version
    'bom-ref' = "app:$ApplicationName@$Version"
})

# A package library listed by the .NET dependency manifest is a resolved app dependency.
foreach ($property in $deps.libraries.PSObject.Properties | Sort-Object Name) {
    $parts = $property.Name -split '/', 2
    if ($parts.Count -ne 2 -or $property.Value.type -ne 'package') { continue }
    $packageName = $parts[0]; $packageVersion = $parts[1]
    $purl = "pkg:nuget/$([uri]::EscapeDataString($packageName))@$([uri]::EscapeDataString($packageVersion))"
    $components.Add(@{ type = 'library'; name = $packageName; version = $packageVersion; 'bom-ref' = $purl; purl = $purl })
}

# Inventory every shipped file so runtime/native payload components are covered too.
foreach ($file in $files) {
    $relative = [Uri]::UnescapeDataString($payloadUri.MakeRelativeUri([Uri]::new($file.FullName)).ToString()).Replace('\', '/')
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $components.Add(@{
        type = 'file'; name = $relative; 'bom-ref' = "file:$relative"
        hashes = @(@{ alg = 'SHA-256'; content = $hash })
    })
}

$bom = @{
    bomFormat = 'CycloneDX'; specVersion = '1.5'; version = 1
    serialNumber = 'urn:uuid:' + [guid]::NewGuid().ToString()
    metadata = @{
        timestamp = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
        component = @{ type = 'application'; name = $ApplicationName; version = $Version }
        properties = @(@{ name = 'octoship:dependency-source'; value = [IO.Path]::GetFileName($depsFiles[0].Name) })
    }
    components = @($components.ToArray())
}
$destination = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $destination
if (!(Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
$json = $bom | ConvertTo-Json -Depth 30
[IO.File]::WriteAllText($destination, $json + "`n", [Text.UTF8Encoding]::new($false))
Write-Host "Generated CycloneDX SBOM: $destination ($($components.Count) components; $($files.Count) payload files)"
