using System;
using System.Linq;
using System.Text.Json;

namespace FileToGitHub;

public static class WindowsUpdateRelease
{
    public static JsonElement Select(JsonElement releases, bool preview)
    {
        JsonElement selected = default;
        ReleaseVersion? newest = null;
        foreach (var release in releases.EnumerateArray())
        {
            if (release.GetProperty("draft").GetBoolean() || (!preview && release.GetProperty("prerelease").GetBoolean())) continue;
            if (!release.TryGetProperty("assets", out var assets) || !assets.EnumerateArray().Any(asset =>
                asset.TryGetProperty("name", out var name) && string.Equals(name.GetString(), "OctoShip-win-x64.zip", StringComparison.OrdinalIgnoreCase))) continue;
            ReleaseVersion version;
            try { version = ReleaseVersion.Parse(release.GetProperty("tag_name").GetString() ?? ""); }
            catch (InvalidOperationException) { continue; }
            if (!preview && version.Preview.Length != 0) continue;
            if (newest is null || version.CompareTo(newest) > 0) { newest = version; selected = release; }
        }
        return selected;
    }
}
