using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace FileToGitHub;

/// <summary>A local recovery journal. Credentials, file contents and remote authorization are never persisted.</summary>
public sealed class PersistentUploadQueueStore
{
    private readonly string _directory;
    public PersistentUploadQueueStore(string? directory = null) => _directory = directory ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "UploadQueues");
    public sealed record Entry(string SourcePath, string DestinationPath, string CommitMessage, long Length, DateTime LastWriteTimeUtc, string Status, string? Url);
    public sealed record Snapshot(int Version, string Repository, string Branch, int CommitMode, string BatchMessage, Entry[] Entries);
    private string FilePath(string repository, string branch) => Path.Combine(_directory, Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(repository.ToLowerInvariant() + "\n" + branch))) + ".json");
    public Snapshot? Load(string repository, string branch)
    {
        var path = FilePath(repository, branch);
        if (!File.Exists(path)) return null;
        if (new FileInfo(path).Length > 2 * 1024 * 1024) throw new InvalidDataException("The saved queue is too large.");
        var snapshot = JsonSerializer.Deserialize<Snapshot>(File.ReadAllText(path));
        if (snapshot == null || snapshot.Version != 1 || !string.Equals(snapshot.Repository, repository, StringComparison.OrdinalIgnoreCase) || snapshot.Branch != branch || snapshot.Entries == null || snapshot.Entries.Length > 100)
            throw new InvalidDataException("The saved queue is not valid for this repository and branch.");
        foreach (var entry in snapshot.Entries)
        {
            if (string.IsNullOrWhiteSpace(entry.SourcePath) || !Path.IsPathFullyQualified(entry.SourcePath) || entry.Length < 0)
                throw new InvalidDataException("A saved queue file is invalid.");
            UploadQueueItem.NormalizeDestination(entry.DestinationPath);
        }
        return snapshot;
    }
    public void Save(Snapshot snapshot)
    {
        Directory.CreateDirectory(_directory);
        var path = FilePath(snapshot.Repository, snapshot.Branch);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(snapshot));
        File.Move(temporary, path, true);
    }
    public void Delete(string repository, string branch)
    {
        var path = FilePath(repository, branch);
        if (File.Exists(path)) File.Delete(path);
    }
    public static UploadQueueItem RestoreItem(Entry entry) => new(entry.SourcePath, entry.DestinationPath, entry.Length, entry.LastWriteTimeUtc);
}
