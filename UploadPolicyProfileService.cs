using System;
using System.Collections.Generic;
using System.Linq;

namespace FileToGitHub;

/// <summary>Credential-free local rules that constrain the standard file upload review.</summary>
public sealed record UploadPolicyProfile
{
    public string Name { get; init; } = "";
    public string[] IncludePatterns { get; init; } = Array.Empty<string>();
    public string[] ExcludePatterns { get; init; } = Array.Empty<string>();
    public long MaxFileBytes { get; init; } = 50L * 1024 * 1024;
}

public static class UploadPolicyProfileService
{
    private const long AppMaxBytes = 50L * 1024 * 1024;

    public static IReadOnlyList<UploadPolicyProfile> Normalize(IEnumerable<UploadPolicyProfile>? profiles)
    {
        var output = new List<UploadPolicyProfile>();
        foreach (var source in profiles ?? Array.Empty<UploadPolicyProfile>())
        {
            try
            {
                var profile = Validate(source);
                if (output.Any(item => string.Equals(item.Name, profile.Name, StringComparison.OrdinalIgnoreCase))) continue;
                output.Add(profile);
                if (output.Count == 25) break;
            }
            catch (ArgumentException) { }
        }
        return output;
    }

    public static UploadPolicyProfile Validate(UploadPolicyProfile profile)
    {
        ArgumentNullException.ThrowIfNull(profile);
        var name = (profile.Name ?? "").Trim();
        if (name.Length is < 1 or > 60 || name.Any(char.IsControl)) throw new ArgumentException("Profile names must be 1–60 characters and contain no control characters.");
        if (string.Equals(name, "— No profile —", StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("That name is reserved for the no-profile option.");
        if (profile.MaxFileBytes is < 1 or > AppMaxBytes) throw new ArgumentException("Maximum file size must be between 1 byte and 50 MiB.");
        return profile with { Name = name, IncludePatterns = ValidatePatterns(profile.IncludePatterns), ExcludePatterns = ValidatePatterns(profile.ExcludePatterns) };
    }

    /// <returns>A blocking explanation, or null when this destination and file size are allowed.</returns>
    public static string? Check(UploadPolicyProfile profile, string destinationPath, long size)
    {
        ArgumentNullException.ThrowIfNull(profile);
        var path = (destinationPath ?? "").Replace('\\', '/').Trim('/');
        if (size < 0) return "File size could not be confirmed.";
        if (size > profile.MaxFileBytes) return $"{FormatSize(size)} exceeds this profile's {FormatSize(profile.MaxFileBytes)} per-file limit.";
        if (profile.IncludePatterns.Length > 0 && new FileSafetyRules(profile.IncludePatterns).Match(path).Count == 0)
            return "The destination does not match this profile's include patterns.";
        if (new FileSafetyRules(profile.ExcludePatterns).Match(path).Count > 0)
            return "The destination matches an excluded pattern in this profile.";
        return null;
    }

    private static string[] ValidatePatterns(IEnumerable<string>? patterns)
    {
        var result = new List<string>();
        foreach (var raw in patterns ?? Array.Empty<string>())
        {
            var pattern = (raw ?? "").Trim();
            if (pattern.Length == 0) continue;
            if (pattern.Length > 200 || pattern.StartsWith('/') || pattern.Contains('\\') || pattern.Any(char.IsControl)
                || pattern.Split('/').Any(segment => segment is ".." or "."))
                throw new ArgumentException("Patterns must be relative paths or globs, no longer than 200 characters, without control characters, backslashes, or dot segments.");
            if (!result.Contains(pattern, StringComparer.OrdinalIgnoreCase)) result.Add(pattern);
            if (result.Count > 100) throw new ArgumentException("Each profile may contain at most 100 patterns in each list.");
        }
        return result.ToArray();
    }

    private static string FormatSize(long bytes) => bytes < 1024 * 1024 ? $"{bytes / 1024d:0.#} KB" : $"{bytes / (1024d * 1024):0.##} MB";
}
