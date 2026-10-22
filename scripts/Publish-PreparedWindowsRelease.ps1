$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Run-Native([string]$Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Command failed with exit code $LASTEXITCODE" }
}

function Read-Releases([string[]]$JsonLines) {
    $pages = ConvertFrom-Json -InputObject ($JsonLines -join "`n")
    foreach ($page in $pages) { foreach ($release in $page) { $release } }
}

$repository = 'ghostventure/OctoShip'
if ($env:GITHUB_REPOSITORY -ne $repository -or $env:GITHUB_REF -ne 'refs/heads/main' -or !$env:GITHUB_SHA) {
    throw 'Publishing is restricted to the OctoShip main-branch GitHub workflow.'
}

[xml]$project = Get-Content -LiteralPath FileToGitHub.csproj
$version = [string]$project.Project.PropertyGroup.Version
if ($version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') { throw 'Invalid Windows release version.' }
$tag = "v$version"
$output = Join-Path (Get-Location) "installers/release-$version"
$archive = Join-Path $output 'OctoShip-win-x64.zip'
$installer = Join-Path $output "OctoShip-Setup-v$version-win-x64.exe"
$checksums = Join-Path $output 'SHA256SUMS.txt'
$sbom = Join-Path $output 'OctoShip-win-x64-sbom.cdx.json'
$audit = Join-Path $output 'OctoShip-dependency-audit.txt'
foreach ($path in @($archive, $installer, $checksums, $sbom, $audit)) {
    if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "Prepared release asset is missing: $path" }
}

$checksumText = [IO.File]::ReadAllText($checksums)
$archiveMatch = [regex]::Match($checksumText, '(?m)^([0-9a-fA-F]{64})  OctoShip-win-x64\.zip\s*$')
$installerMatch = [regex]::Match($checksumText, "(?m)^([0-9a-fA-F]{64})  OctoShip-Setup-v$([regex]::Escape($version))-win-x64\.exe\s*$")
if (!$archiveMatch.Success -or !$installerMatch.Success) { throw 'The package checksum file is invalid.' }
$expectedHash = $archiveMatch.Groups[1].Value.ToLowerInvariant()
$actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$expectedInstallerHash = $installerMatch.Groups[1].Value.ToLowerInvariant()
$actualInstallerHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash -or $actualInstallerHash -ne $expectedInstallerHash) { throw 'Prepared package or installer changed after attestation.' }

$releaseJson = & gh api --paginate --slurp "repos/$repository/releases?per_page=100"
if ($LASTEXITCODE -ne 0) { throw 'Could not inspect existing releases.' }
$existing = Read-Releases $releaseJson | Where-Object tag_name -EQ $tag | Select-Object -First 1
if ($existing -and !$existing.draft) { Write-Host "$tag is already published."; exit 0 }
if ($existing -and $existing.target_commitish -ne $env:GITHUB_SHA -and $existing.author.login -ne 'github-actions[bot]') {
    throw 'An existing draft belongs to another publisher; review it before retrying.'
}

if (!$existing) {
    Run-Native gh @('release', 'create', $tag, '--repo', $repository, '--target', $env:GITHUB_SHA, '--draft', '--title', "OctoShip for Windows $version", '--generate-notes')
} else {
    Run-Native gh @('api', '--method', 'PATCH', "repos/$repository/releases/$($existing.id)", '-f', "target_commitish=$env:GITHUB_SHA", '--silent')
}
Run-Native gh @('release', 'upload', $tag, $archive, $installer, $checksums, $sbom, $audit, '--repo', $repository, '--clobber')

$releaseJson = & gh api --paginate --slurp "repos/$repository/releases?per_page=100"
if ($LASTEXITCODE -ne 0) { throw 'Could not verify uploaded release.' }
$release = Read-Releases $releaseJson | Where-Object tag_name -EQ $tag | Select-Object -First 1
if (!$release -or !$release.draft) { throw 'Expected a draft release before publishing.' }
$asset = $release.assets | Where-Object name -EQ 'OctoShip-win-x64.zip'
$installerAsset = $release.assets | Where-Object name -EQ (Split-Path $installer -Leaf)
if ($asset.digest -ne "sha256:$actualHash" -or $installerAsset.digest -ne "sha256:$actualInstallerHash") { throw 'GitHub asset digests do not match the attested package and installer. Draft left unpublished.' }

$preview = $version.Contains('-')
Run-Native gh @('release', 'edit', $tag, '--repo', $repository, '--draft=false', "--prerelease=$($preview.ToString().ToLowerInvariant())", "--latest=$((!$preview).ToString().ToLowerInvariant())")
Write-Host "Published attested package: https://github.com/$repository/releases/tag/$tag"
