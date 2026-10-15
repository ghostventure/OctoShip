using System;

namespace FileToGitHub;

/// <summary>Policy for clearing app-copied text without erasing a later clipboard value.</summary>
public static class ClipboardClearPolicy
{
    public static int NormalizeDelay(int seconds) => seconds switch { 30 or 60 or 300 => seconds, _ => 0 };

    public static bool ShouldClear(string? currentClipboardText, string? copiedText, int delaySeconds) =>
        NormalizeDelay(delaySeconds) > 0 && !string.IsNullOrEmpty(copiedText) &&
        string.Equals(currentClipboardText, copiedText, StringComparison.Ordinal);
}
