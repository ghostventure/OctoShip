using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace FileToGitHub;

public static class SecurityBoundaries
{
    public static FileStream OpenRead(string path)
    {
        RequireRegularPath(path);
        var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 131072, true);
        try
        {
            var final = new StringBuilder(32768);
            var length = GetFinalPathNameByHandle(stream.SafeFileHandle, final, (uint)final.Capacity, 0);
            if (length == 0 || length >= final.Capacity) throw new IOException("Cannot verify the opened source path.");
            var resolved = final.ToString();
            if (resolved.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase)) resolved = @"\\" + resolved[8..];
            else if (resolved.StartsWith(@"\\?\", StringComparison.Ordinal)) resolved = resolved[4..];
            if (!resolved.Equals(Path.GetFullPath(path), StringComparison.OrdinalIgnoreCase))
                throw new IOException("Source path changed or resolves through a link. Review a regular file instead.");
            RequireRegularPath(path);
            return stream;
        }
        catch { stream.Dispose(); throw; }
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern uint GetFinalPathNameByHandle(SafeFileHandle file, StringBuilder path, uint length, uint flags);
    public static void RequireRegularPath(string path)
    {
        for (var current = Path.GetFullPath(path); !string.IsNullOrEmpty(current); current = Path.GetDirectoryName(current))
            if ((File.Exists(current) || Directory.Exists(current)) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException("Symbolic links and junctions are not supported for this operation.");
    }
    public static string ReadBoundedJson(string path, int maximumBytes)
    {
        RequireRegularPath(path);
        using var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (input.Length > maximumBytes) throw new InvalidOperationException("The saved document exceeds its size limit.");
        using var reader = new StreamReader(input);
        return reader.ReadToEnd();
    }
    public static string Redact(string value, string? token = null)
    {
        if (!string.IsNullOrEmpty(token)) value = value.Replace(token, "[REDACTED]", StringComparison.Ordinal);
        try { return ShippingInspectionService.Redact(value); }
        catch (System.Text.RegularExpressions.RegexMatchTimeoutException) { return "Diagnostic text withheld because redaction could not finish safely."; }
    }
}

/// <summary>All saved bindings for a repository apply to every publishing workflow.</summary>
public static class PublicationBindings
{
    public static string DefaultPath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "project-bindings.json");
    public static Dictionary<string, ShippingProjectProfile> Load(string? path = null)
    {
        path ??= DefaultPath;
        if (!File.Exists(path)) return new();
        try
        {
            var profiles = JsonSerializer.Deserialize<Dictionary<string, ShippingProjectProfile>>(SecurityBoundaries.ReadBoundedJson(path, 1024 * 1024));
            if (profiles == null || profiles.Count > 1000 || profiles.Any(p => p.Value == null || p.Value.ExpectedAccount == null || !p.Key.Contains('|')))
                throw new InvalidOperationException();
            return profiles;
        }
        catch (Exception ex) when (ex is JsonException or IOException or ArgumentException or InvalidOperationException)
        { throw new InvalidOperationException("Saved publication bindings are invalid. Repair or restore project-bindings.json before publishing; bindings were not ignored."); }
    }
    public static void Validate(string repository, string login, string visibility, string? path = null)
    {
        foreach (var entry in Load(path).Where(p => p.Key[(p.Key.LastIndexOf('|') + 1)..].Equals(repository, StringComparison.OrdinalIgnoreCase)))
        {
            var policy = entry.Value;
            if ((!string.IsNullOrWhiteSpace(policy.ExpectedAccount) && !policy.ExpectedAccount.Equals(login, StringComparison.OrdinalIgnoreCase)) ||
                (policy.Visibility != null && !policy.Visibility.Equals(visibility, StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("Publication blocked by a saved account/visibility binding for this repository. Review all project bindings for this repository before retrying.");
        }
    }
}

public static class TrustedProcess
{
    private static readonly string[] ChildEnvironmentAllowList =
    {
        "SystemRoot", "WINDIR", "SYSTEMDRIVE", "ProgramData", "ALLUSERSPROFILE", "PATH",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "TEMP", "TMP", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA",
        "LOCALAPPDATA", "USERNAME", "USERDOMAIN"
    };

    public static string Resolve(string tool)
    {
        var program = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var candidates = tool switch
        {
            "git" => new[] { Path.Combine(program, "Git", "cmd", "git.exe"), Path.Combine(local, "Programs", "Git", "cmd", "git.exe") },
            "gh" => new[] { Path.Combine(program, "GitHub CLI", "gh.exe"), Path.Combine(local, "Programs", "GitHub CLI", "gh.exe") },
            "code" => new[]
            {
                Path.Combine(local, "Programs", "Microsoft VS Code", "Code.exe"),
                Path.Combine(program, "Microsoft VS Code", "Code.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft VS Code", "Code.exe"),
                Path.Combine(local, "Programs", "Microsoft VS Code Insiders", "Code - Insiders.exe"),
                Path.Combine(program, "Microsoft VS Code Insiders", "Code - Insiders.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft VS Code Insiders", "Code - Insiders.exe")
            },
            "powershell.exe" => new[] { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "WindowsPowerShell", "v1.0", "powershell.exe") },
            "explorer.exe" => new[] { Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Windows), "explorer.exe") },
            _ => throw new InvalidOperationException("Unsupported external tool.")
        };
        var executable = candidates.FirstOrDefault(File.Exists) ?? throw new InvalidOperationException("Install " + tool + " in its standard Windows installation directory. PATH-based executable discovery is disabled.");
        SecurityBoundaries.RequireRegularPath(executable);
        return executable;
    }
    public static ProcessStartInfo Create(string tool)
    {
        AccountSessionLock.ThrowIfLocked();
        var start = new ProcessStartInfo(Resolve(tool)) { UseShellExecute = false, CreateNoWindow = true, WindowStyle = ProcessWindowStyle.Hidden };
        start.WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.System);
        // Git, credential helpers, and tool runtimes may need PATH for dependencies;
        // configured proxies may be essential for GitHub connectivity. Keep those
        // plus standard Windows/user-profile state, but exclude arbitrary caller
        // variables such as GH_TOKEN, GIT_CONFIG_* and shell overrides.
        var inherited = ChildEnvironmentAllowList
            .Select(name => new KeyValuePair<string, string?>(name, Environment.GetEnvironmentVariable(name)))
            .Where(pair => !string.IsNullOrEmpty(pair.Value));
        start.Environment.Clear();
        foreach (var (name, value) in inherited) start.Environment[name] = value;
        start.Environment["GIT_TERMINAL_PROMPT"] = "0";
        start.Environment["GCM_INTERACTIVE"] = "never";
        start.Environment["GH_PROMPT_DISABLED"] = "1";
        return start;
    }
    public static Process Start(ProcessStartInfo start)
    {
        AccountSessionLock.ThrowIfLocked();
        return Process.Start(start) ?? throw new InvalidOperationException("The external tool could not start.");
    }
    public static async Task WaitAsync(Process process, CancellationToken cancellationToken = default, int seconds = 120)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(seconds));
        try { await process.WaitForExitAsync(timeout.Token); }
        catch (OperationCanceledException) { try { process.Kill(entireProcessTree: true); } catch (InvalidOperationException) { } throw; }
    }
}
