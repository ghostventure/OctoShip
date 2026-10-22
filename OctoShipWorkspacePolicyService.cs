using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace FileToGitHub;

/// <summary>Local workspace archive, health, repair, and safe retention operations.</summary>
public static class OctoShipWorkspacePolicyService
{
    public static string DataDirectory => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub");
    private static string ArchivePath => Path.Combine(DataDirectory, "archived-workspaces.json");
    private static readonly string[] RetainableFiles = { "search-workspaces.json", "update-failed.txt" };

    public static IReadOnlyList<string> ReadArchived()
    {
        try { return JsonSerializer.Deserialize<string[]>(File.ReadAllText(ArchivePath)) ?? Array.Empty<string>(); }
        catch { return Array.Empty<string>(); }
    }

    public static bool IsArchived(string workspaceName) => ReadArchived().Contains(workspaceName, StringComparer.OrdinalIgnoreCase);
    /// <summary>True means publishing must be blocked unless the repository is confirmed private.</summary>
    public static bool RequiresPrivateRepository(OctoCatPreferences preferences, string ownerAndName) =>
        preferences.PrivateOnlyRepositories.Contains(ownerAndName, StringComparer.OrdinalIgnoreCase);
    public static bool CanPublishToRepository(OctoCatPreferences preferences, string ownerAndName, bool repositoryIsPrivate) =>
        !RequiresPrivateRepository(preferences, ownerAndName) || repositoryIsPrivate;

    public static void SaveArchived(IEnumerable<string> names)
    {
        Directory.CreateDirectory(DataDirectory);
        var values = names.Where(x => !string.IsNullOrWhiteSpace(x) && x.Length <= 500 && !x.Any(char.IsControl)).Distinct(StringComparer.OrdinalIgnoreCase).Take(100).ToArray();
        var temp = ArchivePath + ".tmp-" + Guid.NewGuid().ToString("N");
        try { File.WriteAllText(temp, JsonSerializer.Serialize(values, new JsonSerializerOptions { WriteIndented = true })); File.Move(temp, ArchivePath, true); }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }

    public static IReadOnlyList<string> HealthReport()
    {
        var report = new List<string>();
        try
        {
            if (!Directory.Exists(DataDirectory)) return new[] { "No OctoShip local data folder exists yet." };
            foreach (var name in new[] { "preferences.json", "settings.json", "search-workspaces.json", "archived-workspaces.json" })
            {
                var path = Path.Combine(DataDirectory, name);
                if (!File.Exists(path)) { report.Add($"{name}: not created."); continue; }
                var info = new FileInfo(path);
                if (info.Length > 8 * 1024 * 1024) report.Add($"{name}: unusually large ({info.Length / 1024:N0} KB); inspect before cleanup.");
                else report.Add($"{name}: available ({info.Length:N0} bytes, updated {info.LastWriteTime:g}).");
                if (name is "preferences.json" or "search-workspaces.json" or "archived-workspaces.json")
                    try { using var _ = JsonDocument.Parse(File.ReadAllText(path)); }
                    catch (JsonException) { report.Add($"{name}: invalid JSON; use Profile repair to back it up before resetting preferences."); }
            }
            var probePath = Path.Combine(DataDirectory, ".health-probe-" + Guid.NewGuid().ToString("N"));
            try { using var probe = new FileStream(probePath, FileMode.CreateNew, FileAccess.Write, FileShare.None); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { report.Add("Data folder is not writable: " + ex.Message); }
            finally { if (File.Exists(probePath)) File.Delete(probePath); }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { report.Add("Could not inspect local data: " + ex.Message); }
        return report;
    }

    public static IReadOnlyList<(string Name, long Bytes)> RetentionInventory() => RetainableFiles
        .Select(name => Path.Combine(DataDirectory, name)).Where(File.Exists).Select(path => (Path.GetFileName(path), new FileInfo(path).Length)).ToArray();

    public static void PurgeRetainable(IEnumerable<string> names)
    {
        var allowed = new HashSet<string>(RetainableFiles, StringComparer.OrdinalIgnoreCase);
        foreach (var name in names.Distinct(StringComparer.OrdinalIgnoreCase))
        {
            if (!allowed.Contains(name)) throw new InvalidOperationException("That file is protected from retention cleanup.");
            var path = Path.Combine(DataDirectory, name);
            if (File.Exists(path)) File.Delete(path);
        }
    }

    public static string RepairPreferences()
    {
        Directory.CreateDirectory(DataDirectory);
        var path = Path.Combine(DataDirectory, "preferences.json");
        if (!File.Exists(path))
        {
            File.WriteAllText(path, JsonSerializer.Serialize(new OctoCatPreferences(), new JsonSerializerOptions { WriteIndented = true }));
            return "A fresh preference profile was created.";
        }
        try { using var _ = JsonDocument.Parse(File.ReadAllText(path)); return "Preferences are valid; no repair was needed."; }
        catch (JsonException)
        {
            var backup = path + ".corrupt-" + DateTime.UtcNow.ToString("yyyyMMdd-HHmmss") + ".bak";
            File.Copy(path, backup, false);
            var temp = path + ".repair-" + Guid.NewGuid().ToString("N");
            try { File.WriteAllText(temp, JsonSerializer.Serialize(new OctoCatPreferences(), new JsonSerializerOptions { WriteIndented = true })); File.Move(temp, path, true); }
            finally { if (File.Exists(temp)) File.Delete(temp); }
            return $"Defaults restored. The previous profile was preserved at {Path.GetFileName(backup)}.";
        }
    }
}
