using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Threading;

namespace FileToGitHub;

public sealed record DuplicateFile(string FullPath, long Length, DateTime LastWriteTimeUtc);

public sealed record DuplicateFileGroup(string Sha256, long Length, IReadOnlyList<DuplicateFile> Files)
{
    public long RedundantBytes => Length * Math.Max(0, Files.Count - 1);
    public string Display => $"{Files.Count} identical files · {FormatSize(Length)} each · {FormatSize(RedundantBytes)} redundant\n" +
        string.Join("\n", Files.Select(file => "  " + file.FullPath));
    private static string FormatSize(long bytes) => bytes < 1024 * 1024 ? $"{bytes / 1024d:0.#} KB" : $"{bytes / (1024d * 1024):0.##} MB";
}

public sealed record DuplicateScanResult(IReadOnlyList<DuplicateFileGroup> Groups, int VisitedEntries, int HashedFiles,
    long HashedBytes, bool Limited, IReadOnlyList<string> Warnings);

/// <summary>Finds byte-identical regular files using size prefiltering and bounded SHA-256 reads.</summary>
public sealed class DuplicateFileFinderService
{
    private static readonly HashSet<string> ExcludedDirectories = new(StringComparer.OrdinalIgnoreCase)
        { ".git", "node_modules", "bin", "obj", ".next", "packages" };
    private const int MaxVisitedEntries = 200_000;
    private const int MaxCandidateFiles = 20_000;
    private const long MaxFileBytes = 256L * 1024 * 1024;
    private const long MaxHashedBytes = 1024L * 1024 * 1024;

    public DuplicateScanResult Scan(string folder, IProgress<(int Visited, int Candidates, long Bytes)>? progress = null,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(folder) || !Directory.Exists(folder)) throw new DirectoryNotFoundException("Choose an existing folder to scan.");
        var root = Path.GetFullPath(folder);
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException("A linked or redirected folder cannot be scanned.");

        var candidatesBySize = new Dictionary<long, List<DuplicateFile>>();
        var warnings = new List<string>();
        var pending = new Stack<string>();
        pending.Push(root);
        var visited = 0;
        var candidateCount = 0;
        var limited = false;
        while (pending.Count > 0)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (visited >= MaxVisitedEntries) { limited = true; break; }
            string[] entries;
            try { entries = Directory.GetFileSystemEntries(pending.Pop()); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            { warnings.Add("An inaccessible directory was skipped."); continue; }
            Array.Sort(entries, StringComparer.OrdinalIgnoreCase);
            foreach (var path in entries)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (++visited > MaxVisitedEntries) { limited = true; break; }
                if ((visited & 255) == 0) progress?.Report((visited, candidateCount, 0));
                try
                {
                    var attributes = File.GetAttributes(path);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) continue;
                    if ((attributes & FileAttributes.Directory) != 0)
                    {
                        if (!ExcludedDirectories.Contains(Path.GetFileName(path))) pending.Push(path);
                        continue;
                    }
                    var info = new FileInfo(path);
                    if (info.Length > MaxFileBytes) { warnings.Add("Some files above 256 MiB were skipped."); continue; }
                    if (!candidatesBySize.TryGetValue(info.Length, out var sameSize)) candidatesBySize[info.Length] = sameSize = new List<DuplicateFile>();
                    sameSize.Add(new DuplicateFile(path, info.Length, info.LastWriteTimeUtc));
                    if (++candidateCount >= MaxCandidateFiles) { limited = true; break; }
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException)
                { warnings.Add("Some files could not be inspected and were skipped."); }
            }
            if (limited) break;
        }

        var hashGroups = new Dictionary<(long Size, string Hash), List<DuplicateFile>>();
        var hashedFiles = 0;
        long hashedBytes = 0;
        foreach (var sizeGroup in candidatesBySize.Where(pair => pair.Value.Count > 1).OrderBy(pair => pair.Key))
        {
            foreach (var file in sizeGroup.Value)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (sizeGroup.Key > MaxHashedBytes - hashedBytes) { limited = true; warnings.Add("The 1 GiB content-hash budget was reached; remaining files were not checked."); break; }
                try
                {
                    var info = new FileInfo(file.FullPath);
                    if (!info.Exists || info.Length != file.Length || info.LastWriteTimeUtc != file.LastWriteTimeUtc)
                    { warnings.Add("A file changed during scanning and was skipped."); continue; }
                    using var input = new FileStream(file.FullPath, FileMode.Open, FileAccess.Read, FileShare.Read, 64 * 1024, FileOptions.SequentialScan);
                    var digest = Convert.ToHexString(SHA256.HashData(input, cancellationToken));
                    info.Refresh();
                    if (!info.Exists || info.Length != file.Length || info.LastWriteTimeUtc != file.LastWriteTimeUtc)
                    { warnings.Add("A file changed during hashing and was skipped."); continue; }
                    var key = (file.Length, digest);
                    if (!hashGroups.TryGetValue(key, out var sameContent)) hashGroups[key] = sameContent = new List<DuplicateFile>();
                    sameContent.Add(file);
                    hashedFiles++; hashedBytes += file.Length;
                    if ((hashedFiles & 15) == 0) progress?.Report((visited, hashedFiles, hashedBytes));
                }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or CryptographicException)
                { warnings.Add("Some candidate files could not be hashed and were skipped."); }
            }
            if (limited) break;
        }

        var groups = hashGroups.Where(pair => pair.Value.Count > 1)
            .Select(pair => new DuplicateFileGroup(pair.Key.Hash, pair.Key.Size, pair.Value.OrderBy(file => file.FullPath, StringComparer.OrdinalIgnoreCase).ToArray()))
            .OrderByDescending(group => group.RedundantBytes).ThenBy(group => group.Files[0].FullPath, StringComparer.OrdinalIgnoreCase).ToArray();
        return new DuplicateScanResult(groups, visited, hashedFiles, hashedBytes, limited, warnings.Distinct(StringComparer.Ordinal).ToArray());
    }
}
