using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

public sealed record SecretFinding(string Kind, int Line);
public sealed record SecretScanResult(IReadOnlyList<SecretFinding> Findings, string Status, bool Complete)
{
    public bool HasFindings => Findings.Count != 0;
    public string Summary => Status + (HasFindings ? "\n" + string.Join("\n", Findings.Select(f => $"{f.Kind} near line {f.Line} (value hidden)")) : "");
}

/// <summary>Heuristic local scan. Never returns matched values; not a guarantee that content is safe.</summary>
public static class ContentSecretScanner
{
    public const int MaximumBytes = 2 * 1024 * 1024;
    private static readonly (string Name, Regex Pattern)[] Rules =
    {
        Rule("Private key", @"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"),
        Rule("GitHub token", @"\b(?:gh[pousr]_[A-Za-z0-9]{20,255}|github_pat_[A-Za-z0-9_]{20,255})\b"),
        Rule("AWS access key ID", @"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        Rule("Slack token", @"\bxox[baprs]-[A-Za-z0-9-]{20,255}\b"),
        Rule("Google API key", @"\bAIza[A-Za-z0-9_-]{35}\b"),
        Rule("Possible unquoted credential assignment", @"(?im)^\s*(?:export\s+)?(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|secret[_-]?key)\s*[:=]\s*[^\s\x22'${<][^\s#]{7,255}\s*$"),
        Rule("Possible credential assignment", "(?im)\\b(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|secret[_-]?key)\\b[\\\"']?\\s*[:=]\\s*[\\\"'][^\\\"'\\r\\n]{8,256}[\\\"']")
    };
    private static (string, Regex) Rule(string name, string pattern) => (name, new Regex(pattern, RegexOptions.CultureInvariant, TimeSpan.FromMilliseconds(150)));

    public static async Task<SecretScanResult> ScanAsync(string path, CancellationToken cancellationToken = default)
    {
        try
        {
            await using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 8192, true);
            if (stream.Length > MaximumBytes) return new(Array.Empty<SecretFinding>(), "Not scanned: file exceeds the 2 MiB content-scan limit.", false);
            var bytes = new byte[(int)stream.Length];
            var offset = 0;
            while (offset < bytes.Length)
            {
                var count = await stream.ReadAsync(bytes.AsMemory(offset), cancellationToken);
                if (count == 0) break;
                offset += count;
            }
            if (offset != bytes.Length) return new(Array.Empty<SecretFinding>(), "Not scanned: file changed while reading.", false);
            return ScanBytes(bytes, cancellationToken);
        }
        catch (IOException) { return new(Array.Empty<SecretFinding>(), "Not scanned: file could not be read.", false); }
        catch (UnauthorizedAccessException) { return new(Array.Empty<SecretFinding>(), "Not scanned: file access denied.", false); }
    }

    public static SecretScanResult ScanBytes(byte[] bytes, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (bytes.Length > MaximumBytes) return new(Array.Empty<SecretFinding>(), "Not scanned: file exceeds the 2 MiB content-scan limit.", false);
        try
        {
            string content;
            if (bytes.Length >= 2 && bytes[0] == 0xff && bytes[1] == 0xfe) content = new UnicodeEncoding(false, true, true).GetString(bytes, 2, bytes.Length - 2);
            else if (bytes.Length >= 2 && bytes[0] == 0xfe && bytes[1] == 0xff) content = new UnicodeEncoding(true, true, true).GetString(bytes, 2, bytes.Length - 2);
            else
            {
                if (bytes.Contains((byte)0)) return new(Array.Empty<SecretFinding>(), "Not scanned: binary content or unsupported text encoding. Archives are not unpacked.", false);
                content = new UTF8Encoding(false, true).GetString(bytes);
            }
            return ScanText(content, cancellationToken);
        }
        catch (DecoderFallbackException) { return new(Array.Empty<SecretFinding>(), "Not scanned: unsupported text encoding.", false); }
    }

    public static SecretScanResult ScanText(string content, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (content.Length > MaximumBytes) return new(Array.Empty<SecretFinding>(), "Not scanned: content exceeds the scan limit.", false);
        var findings = new List<SecretFinding>();
        try
        {
            foreach (var rule in Rules)
            {
                cancellationToken.ThrowIfCancellationRequested();
                foreach (Match match in rule.Pattern.Matches(content))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    var line = 1;
                    for (var i = 0; i < match.Index; i++) if (content[i] == '\n') line++;
                    findings.Add(new SecretFinding(rule.Name, line));
                    if (findings.Count >= 30) return new(findings, "Scan stopped after 30 potential secrets. Review the entire file.", false);
                }
            }
            return new(findings, findings.Count == 0 ? "No supported secret patterns detected. Heuristic scan cannot prove a file is safe." : "Potential secrets detected. Review before uploading.", true);
        }
        catch (RegexMatchTimeoutException) { return new(findings, "Scan incomplete: pattern time limit reached.", false); }
    }
}
