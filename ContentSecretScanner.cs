using System;
using System.Collections.Generic;
using System.Diagnostics;
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
    public static readonly TimeSpan MaximumScanDuration = TimeSpan.FromSeconds(2);
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
        var started = Stopwatch.GetTimestamp();
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        deadline.CancelAfter(MaximumScanDuration);
        try
        {
            await using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 8192, true);
            if (stream.Length > MaximumBytes) return new(Array.Empty<SecretFinding>(), "Not scanned: file exceeds the 2 MiB content-scan limit.", false);
            var bytes = new byte[(int)stream.Length];
            var offset = 0;
            while (offset < bytes.Length)
            {
                var count = await stream.ReadAsync(bytes.AsMemory(offset), deadline.Token);
                if (count == 0) break;
                offset += count;
            }
            if (offset != bytes.Length) return new(Array.Empty<SecretFinding>(), "Not scanned: file changed while reading.", false);
            var remaining = MaximumScanDuration - Stopwatch.GetElapsedTime(started);
            if (remaining <= TimeSpan.Zero) return new(Array.Empty<SecretFinding>(), "Not scanned: total per-file time budget reached.", false);
            return ScanBytes(bytes, cancellationToken, remaining);
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
        { return new(Array.Empty<SecretFinding>(), "Not scanned: total per-file time budget reached.", false); }
        catch (IOException) { return new(Array.Empty<SecretFinding>(), "Not scanned: file could not be read.", false); }
        catch (UnauthorizedAccessException) { return new(Array.Empty<SecretFinding>(), "Not scanned: file access denied.", false); }
    }

    public static SecretScanResult ScanBytes(byte[] bytes, CancellationToken cancellationToken = default)
        => ScanBytes(bytes, cancellationToken, MaximumScanDuration);

    public static SecretScanResult ScanBytes(byte[] bytes, CancellationToken cancellationToken, TimeSpan timeBudget)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (bytes.Length > MaximumBytes) return new(Array.Empty<SecretFinding>(), "Not scanned: file exceeds the 2 MiB content-scan limit.", false);
        if (timeBudget <= TimeSpan.Zero || timeBudget > MaximumScanDuration)
            throw new ArgumentOutOfRangeException(nameof(timeBudget), "The scan budget must be positive and no more than two seconds.");
        var started = Stopwatch.GetTimestamp();
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
            var remaining = timeBudget - Stopwatch.GetElapsedTime(started);
            if (remaining <= TimeSpan.Zero) return new(Array.Empty<SecretFinding>(), "Not scanned: total per-file time budget reached.", false);
            return ScanText(content, cancellationToken, remaining);
        }
        catch (DecoderFallbackException) { return new(Array.Empty<SecretFinding>(), "Not scanned: unsupported text encoding.", false); }
    }

    public static SecretScanResult ScanText(string content, CancellationToken cancellationToken = default)
        => ScanText(content, cancellationToken, MaximumScanDuration);

    public static SecretScanResult ScanText(string content, CancellationToken cancellationToken, TimeSpan timeBudget)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (content.Length > MaximumBytes) return new(Array.Empty<SecretFinding>(), "Not scanned: content exceeds the scan limit.", false);
        if (timeBudget <= TimeSpan.Zero || timeBudget > MaximumScanDuration)
            throw new ArgumentOutOfRangeException(nameof(timeBudget), "The scan budget must be positive and no more than two seconds.");
        var started = Stopwatch.GetTimestamp();
        var findings = new List<SecretFinding>();
        try
        {
            foreach (var rule in Rules)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (Stopwatch.GetElapsedTime(started) >= timeBudget)
                    return new(findings, "Scan incomplete: total per-file time budget reached.", false);
                foreach (Match match in rule.Pattern.Matches(content))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    if (Stopwatch.GetElapsedTime(started) >= timeBudget)
                        return new(findings, "Scan incomplete: total per-file time budget reached.", false);
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
