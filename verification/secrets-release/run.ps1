$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$verificationRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('OctoShip-secret-release-verify-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $verificationRoot | Out-Null
$escapedRoot = [System.Security.SecurityElement]::Escape($repositoryRoot)
$project = @"
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType><TargetFramework>net6.0-windows</TargetFramework>
    <UseWPF>true</UseWPF><UseWindowsForms>true</UseWindowsForms><Nullable>enable</Nullable><EnableDefaultCompileItems>false</EnableDefaultCompileItems>
  </PropertyGroup>
  <ItemGroup>
    <ProjectReference Include="$escapedRoot\FileToGitHub.csproj" />
    <Compile Include="$escapedRoot\verification\secrets-release\Program.cs.txt" />
  </ItemGroup>
</Project>
"@
$projectPath = Join-Path $verificationRoot 'Tests.csproj'
Set-Content -LiteralPath $projectPath -Value $project -Encoding UTF8
& dotnet run --project $projectPath
if ($LASTEXITCODE -ne 0) { throw "Verification failed with exit code $LASTEXITCODE" }
