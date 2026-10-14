using System;

namespace FileToGitHub;

public static class UpdateInstaller
{
    // Keep the tested helper identical for automatic closure and manual restart.
    public static string BuildScript(string staging, string appDirectory, string failureMarker, int processId, bool restart)
    {
        return "$ErrorActionPreference='Stop';"
            + "$parent=" + processId + ";"
            + "$src=" + Literal(staging) + ";"
            + "$dst=" + Literal(appDirectory) + ";"
            + "$marker=" + Literal(failureMarker) + ";"
            + "while(Get-Process -Id $parent -ErrorAction SilentlyContinue){Start-Sleep -Milliseconds 300};"
            + "$backup=Join-Path (Split-Path $src) 'backup';New-Item -ItemType Directory -Path $backup -Force|Out-Null;"
            + "try{Copy-Item -Path (Join-Path $dst '*') -Destination $backup -Recurse -Force;Copy-Item -Path (Join-Path $src '*') -Destination $dst -Recurse -Force;"
            + "if(Test-Path -LiteralPath $marker){Remove-Item -LiteralPath $marker -Force}}"
            + "catch{$reason=$_.Exception.Message;try{Copy-Item -Path (Join-Path $backup '*') -Destination $dst -Recurse -Force}catch{};[IO.File]::WriteAllText($marker,$reason);exit 1}"
            + (restart ? ";Start-Process -FilePath (Join-Path $dst 'OctoShip.exe')" : "");
    }

    private static string Literal(string value) => "'" + value.Replace("'", "''") + "'";
}
