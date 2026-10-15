using System;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.Json;

namespace FileToGitHub;

public static class UpdateInstaller
{
    // Keep the tested helper identical for automatic closure and manual restart.
    public static string BuildScript(string staging, string appDirectory, string failureMarker, int processId, bool restart)
    {
        SecurityBoundaries.RequireRegularPath(staging);
        SecurityBoundaries.RequireRegularPath(appDirectory);
        var files = Directory.GetFiles(staging, "*", SearchOption.AllDirectories);
        foreach (var file in files) SecurityBoundaries.RequireRegularPath(file);
        var manifest = files.Select(file => new { Path = Path.GetRelativePath(staging, file), Hash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(file))) }).ToArray();
        return "$ErrorActionPreference='Stop';"
            + "$parent=" + processId + ";"
            + "$src=" + Literal(staging) + ";"
            + "$dst=" + Literal(appDirectory) + ";"
            + "$marker=" + Literal(failureMarker) + ";"
            + "$files=ConvertFrom-Json " + Literal(JsonSerializer.Serialize(manifest)) + ";"
            + "while(Get-Process -Id $parent -ErrorAction SilentlyContinue){Start-Sleep -Milliseconds 300};"
            + "function Check-Payload{param($root) foreach($f in $files){$p=Join-Path $root $f.Path;if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $f.Hash){throw 'Verified update payload changed'}}};"
            + "if((Get-ChildItem -LiteralPath $src -Recurse -Force|Where-Object {($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0}).Count -gt 0){throw 'Linked update payload rejected'};"
            + "if(@(Get-ChildItem -LiteralPath $src -File -Recurse -Force).Count -ne $files.Count){throw 'Update file inventory changed'};Check-Payload $src;"
            + "$backup=Join-Path (Split-Path $src) 'backup';New-Item -ItemType Directory -Path $backup -Force|Out-Null;"
            + "try{Copy-Item -Path (Join-Path $dst '*') -Destination $backup -Recurse -Force;Copy-Item -Path (Join-Path $src '*') -Destination $dst -Recurse -Force;Check-Payload $dst;"
            + "if(Test-Path -LiteralPath $marker){Remove-Item -LiteralPath $marker -Force}}"
            + "catch{$reason=$_.Exception.Message;try{Copy-Item -Path (Join-Path $backup '*') -Destination $dst -Recurse -Force}catch{};[IO.File]::WriteAllText($marker,$reason);exit 1}"
            + (restart ? ";Start-Process -FilePath (Join-Path $dst 'OctoShip.exe')" : "");
    }

    private static string Literal(string value) => "'" + value.Replace("'", "''") + "'";
}
