param([switch]$PackageOnly, [switch]$PrepareRelease)
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

[xml]$project = Get-Content -LiteralPath FileToGitHub.csproj
$version = [string]$project.Project.PropertyGroup.Version
if ($version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') { throw 'Invalid Windows release version.' }
$tag = "v$version"
$repository = 'ghostventure/OctoShip'
$existing = $null
if (!$PackageOnly) {
    if ($env:GITHUB_REPOSITORY -ne $repository -or $env:GITHUB_REF -ne 'refs/heads/main') {
        throw 'Publishing is restricted to the OctoShip main-branch GitHub workflow. Use -PackageOnly locally.'
    }
    # A failed API request must stop publication, not be mistaken for a missing release.
    $json = & gh api --paginate --slurp "repos/$repository/releases?per_page=100"
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect existing releases.' }
    $existing = Read-Releases $json | Where-Object tag_name -EQ $tag | Select-Object -First 1
    if ($existing -and !$existing.draft) { Write-Host "$tag is already published; bump the project version for another update."; exit 0 }
    if ($existing -and $existing.target_commitish -ne $env:GITHUB_SHA -and $existing.author.login -ne 'github-actions[bot]') {
        throw 'An existing draft belongs to another publisher; review it before retrying.'
    }
}

Run-Native dotnet @('build', 'FileToGitHub.csproj', '-c', 'Release')
foreach ($checks in @('updates/UpdateChecks', 'session-lock/SessionLockChecks', 'uploads/AtomicUploadChecks', 'repository-workflows/WorkflowTests', 'uniform-ui/UniformUiChecks', 'p0-security/P0SecurityChecks', 'preparation/PreparationChecks', 'shipping-workbench/ShippingWorkbenchChecks', 'environment/EnvironmentChecks', 'destructive-actions/DestructiveActionChecks', 'account-onboarding/AccountOnboardingChecks')) {
    Run-Native dotnet @('run', '--project', "verification/$checks.csproj", '-c', 'Release')
}
& (Join-Path (Get-Location) 'verification/sbom/Test-ReleaseSbom.ps1')
$output = Join-Path (Get-Location) "installers/release-$version"
$auditLines = & dotnet list FileToGitHub.csproj package --vulnerable --include-transitive 2>&1
if ($LASTEXITCODE -ne 0) { throw 'NuGet vulnerability audit failed; package creation stopped.' }
$auditPath = Join-Path $output 'OctoShip-dependency-audit.txt'
if (!(Test-Path -LiteralPath $output)) { New-Item -ItemType Directory -Path $output -Force | Out-Null }
[IO.File]::WriteAllText($auditPath, "Dependency vulnerability audit`nGenerated UTC: $([DateTime]::UtcNow.ToString('o'))`nCommand: dotnet list FileToGitHub.csproj package --vulnerable --include-transitive`n`n$($auditLines -join "`n")`n", [Text.UTF8Encoding]::new($false))
Write-Host ($auditLines -join "`n")
$payload = Join-Path $output ('payload-' + [guid]::NewGuid().ToString('N'))
Run-Native dotnet @('publish', 'FileToGitHub.csproj', '-c', 'Release', '-r', 'win-x64', '--self-contained', 'true', '-p:DebugType=None', '-o', $payload)
foreach ($runtimeFile in @('coreclr.dll', 'hostfxr.dll')) {
    if (!(Test-Path -LiteralPath (Join-Path $payload $runtimeFile))) { throw "Self-contained package is missing $runtimeFile." }
}
$machineProfileFiles = @('settings.json', 'preferences.json', 'display.json', 'session.json', 'project-bindings.json')
$includedProfileFiles = Get-ChildItem -LiteralPath $payload -File -Recurse | Where-Object { $machineProfileFiles -contains $_.Name }
if ($includedProfileFiles) { throw 'Release payload contains machine-specific OctoShip profile data.' }
$includedQueueData = Get-ChildItem -LiteralPath (Join-Path $payload 'UploadQueues') -File -ErrorAction SilentlyContinue
if ($includedQueueData) { throw 'Release payload contains machine-specific upload queue data.' }
$actualVersion = [Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $payload 'OctoShip.dll')).ProductVersion.Split('+')[0]
if ($actualVersion -ne $version) { throw 'Packaged DLL does not match release version.' }
$archive = Join-Path $output 'OctoShip-win-x64.zip'
Compress-Archive -Path (Join-Path $payload '*') -DestinationPath $archive -Force
$sbom = Join-Path $output 'OctoShip-win-x64-sbom.cdx.json'
& (Join-Path (Get-Location) 'scripts/New-ReleaseSbom.ps1') -PayloadDirectory $payload -OutputPath $sbom -ApplicationName 'OctoShip for GitHub' -Version $version
$hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $output 'SHA256SUMS.txt'), "$hash  OctoShip-win-x64.zip`n")
Write-Host "Verified package: $archive ($hash)"
if ($PackageOnly -or $PrepareRelease) { exit 0 }

if (!$existing) {
    Run-Native gh @('release', 'create', $tag, '--repo', $repository, '--target', $env:GITHUB_SHA, '--draft', '--title', "OctoShip for Windows $version", '--generate-notes')
} else {
    Run-Native gh @('api', '--method', 'PATCH', "repos/$repository/releases/$($existing.id)", '-f', "target_commitish=$env:GITHUB_SHA", '--silent')
}
Run-Native gh @('release', 'upload', $tag, $archive, (Join-Path $output 'SHA256SUMS.txt'), $sbom, $auditPath, '--repo', $repository, '--clobber')
# The by-tag REST endpoint does not return unpublished drafts. Resolve the draft
# through the authenticated release list, as gh release upload itself does.
$releaseJson = & gh api --paginate --slurp "repos/$repository/releases?per_page=100"
if ($LASTEXITCODE -ne 0) { throw 'Could not verify uploaded release.' }
$release = Read-Releases $releaseJson | Where-Object tag_name -EQ $tag | Select-Object -First 1
if (!$release -or !$release.draft) { throw 'Expected a draft release before publishing.' }
$asset = $release.assets | Where-Object name -EQ 'OctoShip-win-x64.zip'
if ($asset.digest -ne "sha256:$hash") { throw 'GitHub asset digest does not match the local package. Draft left unpublished.' }
$preview = $version.Contains('-')
Run-Native gh @('release', 'edit', $tag, '--repo', $repository, '--draft=false', "--prerelease=$($preview.ToString().ToLowerInvariant())", "--latest=$((!$preview).ToString().ToLowerInvariant())")
Write-Host "Published https://github.com/$repository/releases/tag/$tag"
