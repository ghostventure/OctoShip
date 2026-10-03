using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace FileToGitHub;

/// <summary>Evaluates filename/path rules before an upload. Patterns use glob syntax (* and ?).</summary>
public sealed class FileSafetyRules
{
    public static IReadOnlyList<string> DefaultPatterns { get; } = new[]
    {
        ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
        "*credential*", "*secret*", "*password*", "*.publishsettings", "*.keystore"
    };

    public FileSafetyRules(IEnumerable<string>? patterns = null)
    {
        Patterns = (patterns ?? DefaultPatterns).Where(p => !string.IsNullOrWhiteSpace(p))
            .Select(p => p.Trim()).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
    }

    public IReadOnlyList<string> Patterns { get; }

    public IReadOnlyList<string> Match(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) return Array.Empty<string>();
        var normalized = path.Replace('\\', '/');
        var name = Path.GetFileName(normalized);
        return Patterns.Where(pattern => Glob(pattern).IsMatch(name) || Glob(pattern).IsMatch(normalized)).ToArray();
    }

    public static FileSafetyRules ParseLines(string? text) =>
        new((text ?? string.Empty).Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .Select(p => p.Trim()).Where(p => !p.StartsWith("#", StringComparison.Ordinal)));

    private static Regex Glob(string pattern)
    {
        var expression = "^" + Regex.Escape(pattern).Replace("\\*", ".*").Replace("\\?", ".") + "$";
        return new Regex(expression, RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
            TimeSpan.FromMilliseconds(100));
    }
}
