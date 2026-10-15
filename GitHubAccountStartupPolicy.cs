using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace FileToGitHub;

/// <summary>Prevents a new OctoShip profile from silently adopting a Windows GCM account.</summary>
public static class GitHubAccountStartupPolicy
{
    public static bool ResolveAutoConnect(JsonElement savedSettings, string? savedAccount)
    {
        if (savedSettings.TryGetProperty("autoConnect", out var value)
            && value.ValueKind is JsonValueKind.True or JsonValueKind.False)
            return value.GetBoolean();

        // Preserve prior opt-in behavior for existing profiles that already remembered an account.
        // A fresh profile has no saved account, so auto-connect starts disabled.
        return !string.IsNullOrWhiteSpace(savedAccount);
    }

    public static string? ChooseAccount(IEnumerable<string> availableAccounts, params string?[] preferredAccounts)
    {
        var accounts = availableAccounts.ToArray();
        foreach (var preferred in preferredAccounts)
        {
            if (string.IsNullOrWhiteSpace(preferred)) continue;
            var match = accounts.FirstOrDefault(account => string.Equals(account, preferred, StringComparison.OrdinalIgnoreCase));
            if (match is not null) return match;
        }

        // Do not select the only Windows-saved credential implicitly on a fresh app profile.
        return null;
    }
}
