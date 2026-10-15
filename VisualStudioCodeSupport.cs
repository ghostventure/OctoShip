using System;
using System.Diagnostics;
using System.IO;

namespace FileToGitHub;

public static class VisualStudioCodeSupport
{
    public static ProcessStartInfo CreateOpenStartInfo(string path)
    {
        var fullPath = Path.GetFullPath(path);
        var isDirectory = Directory.Exists(fullPath);
        var isFile = File.Exists(fullPath);
        if (!isDirectory && !isFile)
            throw new FileNotFoundException("Choose an existing file or folder to open in VS Code.", fullPath);

        var start = TrustedProcess.Create("code");
        start.CreateNoWindow = false;
        start.WindowStyle = ProcessWindowStyle.Normal;
        start.WorkingDirectory = isDirectory ? fullPath : Path.GetDirectoryName(fullPath)!;
        start.ArgumentList.Add("--reuse-window");

        // VS Code recognizes workspace files directly; --goto is for ordinary files.
        if (isFile && !Path.GetExtension(fullPath).Equals(".code-workspace", StringComparison.OrdinalIgnoreCase))
            start.ArgumentList.Add("--goto");
        start.ArgumentList.Add(fullPath);
        return start;
    }

    public static void Open(string path) => TrustedProcess.Start(CreateOpenStartInfo(path));
}
