using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace FileToGitHub;

/// <summary>Finds repository paths that may be interpreted differently by Windows, Git, or reviewers.</summary>
public static class UploadPathAudit
{
    private static readonly HashSet<string> ReservedNames = BuildReservedNames();
    private static readonly HashSet<int> DirectionalOrInvisible = new()
    {
        0x00AD, 0x034F, 0x061C, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180E,
        0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C,
        0x202D, 0x202E, 0x2060, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF
    };

    /// <summary>Returns actionable warnings; it never rewrites the reviewed destination.</summary>
    public static IReadOnlyList<string> Analyze(IEnumerable<string> destinationPaths)
    {
        ArgumentNullException.ThrowIfNull(destinationPaths);
        var paths = destinationPaths.Where(x => !string.IsNullOrWhiteSpace(x)).ToArray();
        var warnings = new List<string>();
        foreach (var path in paths)
        {
            var segments = path.Replace('\\', '/').Split('/');
            foreach (var segment in segments)
            {
                if (segment.EndsWith(' ') || segment.EndsWith('.'))
                    warnings.Add($"'{path}' has a segment ending in a space or dot, which Windows may remove.");
                var stem = segment.Split('.')[0].TrimEnd(' ', '.');
                if (ReservedNames.Contains(stem))
                    warnings.Add($"'{path}' contains the Windows-reserved name '{stem}'.");
                if (segment.Any(ch => DirectionalOrInvisible.Contains(ch)))
                    warnings.Add($"'{path}' contains an invisible or text-direction control character.");
                if (!string.Equals(segment, segment.Normalize(NormalizationForm.FormC), StringComparison.Ordinal))
                    warnings.Add($"'{path}' is not in Unicode NFC form and may collide with a normalized filename.");
                var hasLatin = false; var hasGreek = false; var hasCyrillic = false;
                foreach (var rune in segment.EnumerateRunes())
                {
                    if (!Rune.IsLetter(rune)) continue;
                    hasLatin |= InRange(rune.Value, 0x0041, 0x024F) || InRange(rune.Value, 0x1E00, 0x1EFF);
                    hasGreek |= InRange(rune.Value, 0x0370, 0x03FF) || InRange(rune.Value, 0x1F00, 0x1FFF);
                    hasCyrillic |= InRange(rune.Value, 0x0400, 0x052F) || InRange(rune.Value, 0x2DE0, 0x2DFF) || InRange(rune.Value, 0xA640, 0xA69F);
                }
                if (hasLatin && (hasGreek || hasCyrillic))
                    warnings.Add($"'{path}' mixes Latin with Greek or Cyrillic letters that may look alike.");
            }
        }

        foreach (var group in paths.GroupBy(CaseFoldPath, StringComparer.Ordinal).Where(g => g.Distinct(StringComparer.Ordinal).Count() > 1))
            warnings.Add($"Multiple destinations differ only by letter case: {string.Join(", ", group)}.");
        foreach (var group in paths.GroupBy(x => x.Normalize(NormalizationForm.FormC), StringComparer.Ordinal).Where(g => g.Distinct(StringComparer.Ordinal).Count() > 1))
            warnings.Add($"Multiple destinations become identical after Unicode normalization: {string.Join(", ", group)}.");

        return warnings.Distinct(StringComparer.Ordinal).Take(30).ToArray();
    }

    private static string CaseFoldPath(string value) => value.Replace('\\', '/').ToUpperInvariant();
    private static bool InRange(int value, int start, int end) => value >= start && value <= end;
    private static HashSet<string> BuildReservedNames()
    {
        var names = new HashSet<string>(new[] { "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$" }, StringComparer.OrdinalIgnoreCase);
        for (var i = 1; i <= 9; i++) { names.Add("COM" + i); names.Add("LPT" + i); }
        return names;
    }
}
