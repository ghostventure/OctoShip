using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Reusable, cancellable local file search. Reparse points are always skipped and never followed.</summary>
public sealed class SearchService
{
    private static readonly string[] DefaultExcludedFolders = { ".git", "node_modules", "bin", "obj", ".next", "packages" };
    private const int AbsoluteMaxResults = 10_000;
    private const int AbsoluteMaxVisited = 2_000_000;
    private const long AbsoluteMaxContentBytes = 50L * 1024 * 1024;

    public async Task<SearchPage> SearchAsync(
        SearchOptions options,
        IProgress<SearchProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(options);
        var validated = Validate(options);
        Regex? regex = null;
        if (validated.QueryMode == SearchQueryMode.RegularExpression)
        {
            try
            {
                regex = new Regex(validated.Query, validated.CaseSensitive ? RegexOptions.None : RegexOptions.IgnoreCase,
                    validated.RegexTimeout);
            }
            catch (ArgumentException ex)
            {
                throw new ArgumentException($"The search expression is invalid: {ex.Message}", nameof(options), ex);
            }
        }

        var roots = new List<string>();
        foreach (var root in validated.RootFolders)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var full = Path.GetFullPath(root);
            if (!Directory.Exists(full)) continue;
            // A reparse-point root is skipped just like a reparse-point child.
            try
            {
                if ((File.GetAttributes(full) & FileAttributes.ReparsePoint) == 0)
                    roots.Add(full);
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
        roots = roots.Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(p => p, StringComparer.OrdinalIgnoreCase).ToList();

        var excluded = new HashSet<string>(DefaultExcludedFolders, StringComparer.OrdinalIgnoreCase);
        foreach (var name in validated.ExcludedFolderNames)
            if (!string.IsNullOrWhiteSpace(name)) excluded.Add(name.Trim());

        var page = new List<SearchFile>();
        var matchedBeforePage = 0;
        var visited = 0;
        var inaccessible = 0;
        var limited = false;
        var stoppedWithExtra = false;
        var pending = new Stack<string>(roots.AsEnumerable().Reverse());

        while (pending.Count > 0)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (visited >= validated.MaxVisitedEntries) { limited = true; break; }
            var directory = pending.Pop();
            string[] entries;
            try { entries = Directory.GetFileSystemEntries(directory); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            { inaccessible++; continue; }
            Array.Sort(entries, StringComparer.OrdinalIgnoreCase);

            foreach (var path in entries)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (++visited > validated.MaxVisitedEntries) { limited = true; break; }
                if ((visited & 127) == 0)
                    progress?.Report(new SearchProgress(visited, matchedBeforePage + page.Count, Path.GetDirectoryName(path) ?? directory));

                try
                {
                    var attributes = File.GetAttributes(path);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) continue;
                    if (!validated.IncludeHidden && (attributes & FileAttributes.Hidden) != 0) continue;
                    if ((attributes & FileAttributes.Directory) != 0)
                    {
                        if (validated.Recursive && !excluded.Contains(Path.GetFileName(path))) pending.Push(path);
                        continue;
                    }

                    var info = new FileInfo(path);
                    if (validated.Extensions.Count > 0 && !validated.Extensions.Contains(info.Extension,
                            validated.CaseSensitive ? StringComparer.Ordinal : StringComparer.OrdinalIgnoreCase)) continue;
                    if (validated.MinBytes is long min && info.Length < min) continue;
                    if (validated.MaxBytes is long max && info.Length > max) continue;
                    if (validated.ModifiedAfter is DateTime modified && info.LastWriteTime.Date < modified.Date) continue;

                    var name = info.Name;
                    var filenameMatch = validated.QueryMode != SearchQueryMode.FileContents &&
                        Matches(name, validated.Query, validated.QueryMode, validated.CaseSensitive, regex, validated.ExactMatch);
                    var contentMatch = false;
                    if (!filenameMatch && validated.QueryMode == SearchQueryMode.FileContents)
                    {
                        if (info.Length <= validated.MaxContentBytes)
                        {
                            try
                            {
                                var contents = await File.ReadAllTextAsync(path, validated.TextEncoding, cancellationToken).ConfigureAwait(false);
                                contentMatch = Matches(contents, validated.Query, validated.QueryMode, validated.CaseSensitive, regex, false);
                            }
                            catch (OperationCanceledException) { throw; }
                            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or DecoderFallbackException)
                            { inaccessible++; continue; }
                        }
                        else continue;
                    }
                    if (!filenameMatch && !contentMatch) continue;

                    if (matchedBeforePage < validated.Offset) { matchedBeforePage++; continue; }
                    if (page.Count == validated.MaxResults) { stoppedWithExtra = true; break; }
                    page.Add(new SearchFile(info.FullName, info.Name, info.Length, info.LastWriteTime, info.LastWriteTimeUtc, contentMatch));
                }
                catch (OperationCanceledException) { throw; }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                { inaccessible++; }
            }
            if (limited || stoppedWithExtra) break;
        }

        var next = stoppedWithExtra ? validated.Offset + page.Count : (int?)null;
        progress?.Report(new SearchProgress(visited, matchedBeforePage + page.Count, null, Complete: !limited));
        return new SearchPage(page, validated.Offset, next, limited, visited, inaccessible,
            "Search never follows reparse points (including junctions and symlinks). Hidden entries are skipped unless IncludeHidden is set. The standard excluded folder names are always excluded; configured names are added to that list.");
    }

    private static bool Matches(string candidate, string query, SearchQueryMode mode, bool caseSensitive, Regex? regex, bool exact)
    {
        if (mode == SearchQueryMode.RegularExpression)
        {
            try { return regex!.IsMatch(candidate); }
            catch (RegexMatchTimeoutException ex) { throw new InvalidOperationException("The regular expression took too long to evaluate. Simplify it and try again.", ex); }
        }
        var comparison = caseSensitive ? StringComparison.Ordinal : StringComparison.OrdinalIgnoreCase;
        return exact ? string.Equals(candidate, query, comparison) : candidate.IndexOf(query, comparison) >= 0;
    }

    private static SearchOptions Validate(SearchOptions o)
    {
        if (o.RootFolders is null || o.RootFolders.Count == 0) throw new ArgumentException("Choose at least one root folder.", nameof(o));
        if (string.IsNullOrWhiteSpace(o.Query)) throw new ArgumentException("Search query cannot be empty.", nameof(o));
        if (o.RootFolders.Any(string.IsNullOrWhiteSpace)) throw new ArgumentException("Root folders cannot be empty.", nameof(o));
        if (o.MaxResults < 1 || o.MaxResults > AbsoluteMaxResults) throw new ArgumentOutOfRangeException(nameof(o.MaxResults), $"Maximum results must be between 1 and {AbsoluteMaxResults}.");
        if (o.Offset < 0) throw new ArgumentOutOfRangeException(nameof(o.Offset));
        if (o.MaxVisitedEntries < 1 || o.MaxVisitedEntries > AbsoluteMaxVisited) throw new ArgumentOutOfRangeException(nameof(o.MaxVisitedEntries));
        if (o.MaxContentBytes < 1 || o.MaxContentBytes > AbsoluteMaxContentBytes) throw new ArgumentOutOfRangeException(nameof(o.MaxContentBytes), $"Content search is capped at {AbsoluteMaxContentBytes} bytes per file.");
        if (o.MinBytes < 0 || o.MaxBytes < 0 || (o.MinBytes.HasValue && o.MaxBytes.HasValue && o.MinBytes > o.MaxBytes))
            throw new ArgumentException("File size bounds are invalid.", nameof(o));
        if (o.RegexTimeout <= TimeSpan.Zero || o.RegexTimeout > TimeSpan.FromSeconds(10)) throw new ArgumentOutOfRangeException(nameof(o.RegexTimeout), "Regex timeout must be positive and at most 10 seconds.");
        if (o.Extensions.Any(e => string.IsNullOrWhiteSpace(e))) throw new ArgumentException("Extensions cannot contain empty values.", nameof(o));
        return o with
        {
            RootFolders = o.RootFolders.ToArray(),
            Extensions = o.Extensions.Select(e => e.StartsWith(".", StringComparison.Ordinal) ? e : "." + e).ToArray(),
            ExcludedFolderNames = o.ExcludedFolderNames.ToArray()
        };
    }
}

public enum SearchQueryMode
{
    FileName,
    RegularExpression,
    FileContents
}

/// <summary>Options are immutable by convention; roots can contain any number of directories.</summary>
public sealed record SearchOptions(
    IReadOnlyList<string> RootFolders,
    string Query,
    SearchQueryMode QueryMode = SearchQueryMode.FileName,
    bool ExactMatch = false,
    bool CaseSensitive = false,
    bool Recursive = true,
    bool IncludeHidden = false,
    IReadOnlyList<string>? Extensions = null,
    IReadOnlyList<string>? ExcludedFolderNames = null,
    long? MinBytes = null,
    long? MaxBytes = null,
    DateTime? ModifiedAfter = null,
    int MaxResults = 200,
    int Offset = 0,
    int MaxVisitedEntries = 100_000,
    long MaxContentBytes = 2L * 1024 * 1024,
    TimeSpan? RegexTimeoutOverride = null,
    Encoding? TextEncodingOverride = null)
{
    public IReadOnlyList<string> Extensions { get; init; } = Extensions ?? Array.Empty<string>();
    public IReadOnlyList<string> ExcludedFolderNames { get; init; } = ExcludedFolderNames ?? Array.Empty<string>();
    internal TimeSpan RegexTimeout { get; init; } = RegexTimeoutOverride ?? TimeSpan.FromMilliseconds(250);
    internal Encoding TextEncoding { get; init; } = TextEncodingOverride ?? new UTF8Encoding(false, false);
}

public sealed record SearchFile(string FullPath, string Name, long Size, DateTime LastModified, DateTime LastModifiedUtc, bool MatchedContents);

/// <summary>NextOffset is null when the scan found no further page; when Limited is true, continue by raising MaxVisitedEntries.</summary>
public sealed record SearchPage(
    IReadOnlyList<SearchFile> Items,
    int Offset,
    int? NextOffset,
    bool Limited,
    int VisitedEntries,
    int InaccessibleEntries,
    string TraversalNotes);

public sealed record SearchProgress(int VisitedEntries, int MatchesFound, string? CurrentFolder, bool Complete = false);
