using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection.PortableExecutable;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace FileToGitHub;

public sealed record ShippingFinding(string File, string Check, string Detail);
public sealed record ShippingProjectProfile(string ExpectedAccount, string? Visibility);

/// <summary>Bounded, local-only checks. Never extracts archives or executes inspected files.</summary>
public static class ShippingInspectionService
{
    public static IReadOnlyList<string> EnumerateProject(string root)
    {
        root = Path.GetFullPath(root);
        var result = new List<string>(); var pending = new Stack<string>(); pending.Push(root);
        var directories = 0;
        while (pending.Count > 0)
        {
            var dir = pending.Pop();
            if (++directories > 10000) throw new IOException("Project exceeds 10,000 folders. Choose a smaller folder.");
            if ((File.GetAttributes(dir) & FileAttributes.ReparsePoint) != 0) throw new IOException("Links and junctions are not scanned.");
            foreach (var path in Directory.EnumerateFileSystemEntries(dir))
            {
                if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) continue;
                if (Directory.Exists(path))
                {
                    if (new[] { ".git", "node_modules", "bin", "obj", ".vs" }.Contains(Path.GetFileName(path), StringComparer.OrdinalIgnoreCase)) continue;
                    pending.Push(path);
                }
                else result.Add(path);
                if (result.Count > 10000) throw new IOException("Project exceeds 10,000 files. Choose a smaller folder.");
            }
        }
        return result;
    }

    public static IReadOnlyList<ShippingFinding> Inspect(string root, string expectedVersion)
    {
        var files = EnumerateProject(root); var findings = new List<ShippingFinding>();
        var relative = files.ToDictionary(p => Path.GetRelativePath(root, p).Replace('\\', '/'), p => p, StringComparer.Ordinal);
        foreach (var pair in relative)
        {
            var file = pair.Value; var name = pair.Key; var info = new FileInfo(file);
            if (info.Length > 50L * 1024 * 1024) findings.Add(new(name, "Large file", "Exceeds OctoShip's 50 MiB upload limit. Use Git LFS through Git, or attach a release asset. OctoShip does not create LFS objects."));
            if (Path.GetFileName(file) == ".gitattributes" && info.Length <= 1024 * 1024 && File.ReadAllText(file).Contains("filter=lfs", StringComparison.Ordinal))
                findings.Add(new(name, "Git LFS", "LFS tracking found. Publish matched files with git lfs and git push; uploading raw contents through the API bypasses LFS."));
            if (Path.GetExtension(file).Equals(".md", StringComparison.OrdinalIgnoreCase) && info.Length <= 1024 * 1024)
                findings.AddRange(CheckMarkdown(root, file));
            if (info.Length <= 1024 * 1024 && (Path.GetExtension(file) is ".csproj" or ".iss" || Path.GetFileName(file) == "package.json"))
            {
                var content = File.ReadAllText(file);
                foreach (Match m in Regex.Matches(content, "(?:<Version>|<AssemblyVersion>|\"version\"\\s*:\\s*\"|#define\\s+\\w*Version\\s+\")(?<v>[^\"<\\r\\n]+)", RegexOptions.IgnoreCase, TimeSpan.FromSeconds(1)))
                {
                    var version = m.Groups["v"].Value.Trim();
                    findings.Add(new(name, "Version", version + (expectedVersion.Length == 0 ? " (no expected version supplied)" : version == expectedVersion.TrimStart('v') ? " — matches" : " — differs from " + expectedVersion)));
                }
            }
            if (expectedVersion.Length > 0 && Path.GetExtension(file) is ".exe" or ".zip" or ".msi")
            {
                var match = Regex.Match(name, @"(?:^|[-_v])(?<v>\d+\.\d+\.\d+)", RegexOptions.None, TimeSpan.FromSeconds(1));
                if (match.Success) findings.Add(new(name, "Asset version", match.Groups["v"].Value + (match.Groups["v"].Value == expectedVersion.TrimStart('v') ? " — matches" : " — differs from " + expectedVersion.TrimStart('v')) + " (filename numeric version only)"));
            }
        }
        findings.Add(new("Project", "Scan coverage", $"Checked {files.Count} files. Excluded .git, node_modules, bin, obj, .vs and links. Text checks limited to 1 MiB per file."));
        return findings;
    }

    public static IReadOnlyList<ShippingFinding> InspectZip(string path)
    {
        if (new FileInfo(path).Length > 512L * 1024 * 1024) throw new IOException("ZIP inspection is limited to archives up to 512 MiB.");
        using var archive = ZipFile.OpenRead(path);
        if (archive.Entries.Count > 10000) throw new IOException("ZIP inspection is limited to 10,000 entries.");
        long total = 0, scanned = 0; var rows = new List<ShippingFinding>();
        foreach (var entry in archive.Entries)
        {
            total = checked(total + entry.Length);
            if (total > 2L * 1024 * 1024 * 1024) throw new IOException("Archive declares over 2 GiB uncompressed. Inspection stopped.");
            var name = entry.FullName.Replace('\\', '/');
            var suspicious = name.StartsWith('/') || name.Contains(':') || name.Split('/').Any(x => x == ".." || x == ".git" || x == "node_modules" || x == ".env" || x.StartsWith(".env.", StringComparison.OrdinalIgnoreCase)) || Regex.IsMatch(name, @"(?i)(id_rsa|id_ed25519|credentials|secrets|\.pfx$|\.pem$|\.key$)");
            var contentStatus = "Content not scanned (directory or scan limit).";
            if (!name.EndsWith('/') && entry.Length <= 512 * 1024 && scanned + entry.Length <= 8 * 1024 * 1024)
            {
                using var source = entry.Open(); using var contents = new MemoryStream(); var buffer = new byte[8192]; int read;
                while ((read = source.Read(buffer, 0, buffer.Length)) > 0)
                {
                    if (contents.Length + read > 512 * 1024 || scanned + read > 8 * 1024 * 1024) throw new IOException("ZIP expansion exceeded the bounded content scan.");
                    contents.Write(buffer, 0, read); scanned += read;
                }
                var scan = ContentSecretScanner.ScanBytes(contents.ToArray()); suspicious |= scan.HasFindings;
                contentStatus = scan.HasFindings ? string.Join(", ", scan.Findings.Select(x => x.Kind)) + " (matched values hidden)." : scan.Status;
            }
            rows.Add(new(name, suspicious ? "Review archive entry" : "Archive entry", $"{entry.Length:N0} bytes; compressed {entry.CompressedLength:N0}. {contentStatus}"));
        }
        return rows;
    }

    public static IReadOnlyList<ShippingFinding> CheckMarkdown(string root, string file)
    {
        var rows = new List<ShippingFinding>();
        foreach (Match match in Regex.Matches(File.ReadAllText(file), @"!?\[[^\]\r\n]*\]\(\s*(?<url><[^>]+>|[^\s)]+)", RegexOptions.None, TimeSpan.FromSeconds(1)))
        {
            var link = match.Groups["url"].Value.Trim('<', '>');
            if (link.StartsWith('#') || link.StartsWith('/') || Uri.TryCreate(link, UriKind.Absolute, out _)) continue;
            link = Uri.UnescapeDataString(link.Split('#', '?')[0]); if (link.Length == 0) continue;
            var target = Path.GetFullPath(Path.Combine(Path.GetDirectoryName(file)!, link.Replace('/', Path.DirectorySeparatorChar)));
            var rel = Path.GetRelativePath(Path.GetFullPath(root), target);
            if (rel == ".." || rel.StartsWith(".." + Path.DirectorySeparatorChar)) { rows.Add(new(Path.GetRelativePath(root, file), "Markdown link", link + " — outside selected project")); continue; }
            var actual = Path.GetFullPath(root); bool missing = false, wrongCase = false;
            foreach (var segment in rel.Split(Path.DirectorySeparatorChar))
            {
                if (!Directory.Exists(actual)) { missing = true; break; }
                var found = Directory.EnumerateFileSystemEntries(actual).Select(Path.GetFileName).FirstOrDefault(x => string.Equals(x, segment, StringComparison.OrdinalIgnoreCase));
                if (found == null) { missing = true; break; }
                wrongCase |= found != segment; actual = Path.Combine(actual, found);
                if ((File.GetAttributes(actual) & FileAttributes.ReparsePoint) != 0) { missing = true; break; }
            }
            if (missing || wrongCase) rows.Add(new(Path.GetRelativePath(root, file), "Markdown link", link + (missing ? " — missing or unsupported link" : " — filename capitalization differs")));
        }
        return rows;
    }

    public static string InspectInstaller(string path)
    {
        var version = FileVersionInfo.GetVersionInfo(path); string architecture;
        try { using var stream = File.OpenRead(path); using var pe = new PEReader(stream); architecture = pe.PEHeaders.CoffHeader.Machine.ToString(); }
        catch (BadImageFormatException) { architecture = "Not a PE executable; MSI package architecture is not inferred"; }
        var signature = OctoCatPreferencesService.VerifyPublisher(path);
        return $"File: {Path.GetFileName(path)}\nVersion: {version.FileVersion ?? "unavailable"}\nProduct version: {version.ProductVersion ?? "unavailable"}\nArchitecture: {architecture}\nSignature: {signature.Message}\nSigner thumbprint: {signature.SignerThumbprint ?? "unavailable"}";
    }

    public static string Redact(string text)
    {
        text = Regex.Replace(text, @"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)", "[PRIVATE KEY REDACTED]", RegexOptions.None, TimeSpan.FromSeconds(1));
        // Redact secrets in both ordinary and percent-encoded URL query strings. Some
        // diagnostics contain URLs that have already been escaped for logs or reports.
        text = Regex.Replace(text, @"((?:[?&]|%3f|%26)(?:access(?:_|%5f)token|client(?:_|%5f)secret|refresh(?:_|%5f)token|id(?:_|%5f)token|token|key|sig|signature|password)(?:=|%3d))(?:(?!&|%26|\s).)+", "$1[REDACTED]", RegexOptions.IgnoreCase, TimeSpan.FromSeconds(1));
        text = Regex.Replace(text, @"(?i)([?&](?:access_token|token|key|sig|signature|password)=)[^&\s]+", "$1[REDACTED]", RegexOptions.None, TimeSpan.FromSeconds(1));
        text = Regex.Replace(text, @"(?i)\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|Bearer\s+\S+)", "[REDACTED]", RegexOptions.None, TimeSpan.FromSeconds(1));
        text = Regex.Replace(text, @"(?im)(token|password|secret|authorization|api[_-]?key)\s*[:=]\s*[^\r\n]+", "$1=[REDACTED]", RegexOptions.None, TimeSpan.FromSeconds(1));
        text = Regex.Replace(text, @"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", RegexOptions.None, TimeSpan.FromSeconds(1));
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        return home.Length == 0 ? text : text.Replace(home, "%USERPROFILE%", StringComparison.OrdinalIgnoreCase);
    }
}
