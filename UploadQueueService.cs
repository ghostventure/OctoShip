using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Collision behavior when a planned GitHub path already exists.</summary>
public enum UploadCollisionPolicy
{
    Skip,
    Rename,
    Replace
}

public enum UploadQueueItemState
{
    Queued,
    Running,
    Succeeded,
    Failed,
    Skipped,
    Cancelled
}

/// <summary>A local file and its intended repository-relative destination.</summary>
public sealed class UploadQueueItem
{
    internal UploadQueueItem(string sourcePath, string destinationPath)
    {
        SourcePath = Path.GetFullPath(sourcePath);
        DestinationPath = NormalizeDestination(destinationPath);
        var info = new FileInfo(SourcePath);
        if (!info.Exists) throw new FileNotFoundException("The selected file does not exist.", SourcePath);
        CapturedLength = info.Length;
        CapturedLastWriteTimeUtc = info.LastWriteTimeUtc;
    }

    internal UploadQueueItem(string sourcePath, string destinationPath, long capturedLength, DateTime capturedLastWriteTimeUtc)
    {
        SourcePath = Path.GetFullPath(sourcePath);
        DestinationPath = NormalizeDestination(destinationPath);
        CapturedLength = capturedLength;
        CapturedLastWriteTimeUtc = capturedLastWriteTimeUtc;
    }

    public string SourcePath { get; }
    public string DestinationPath { get; internal set; }
    public long CapturedLength { get; }
    public DateTime CapturedLastWriteTimeUtc { get; }
    public UploadQueueItemState State { get; internal set; } = UploadQueueItemState.Queued;
    public double ProgressPercent { get; internal set; }
    public string? Error { get; internal set; }

    public bool HasChangedOnDisk()
    {
        var info = new FileInfo(SourcePath);
        return !info.Exists || info.Length != CapturedLength || info.LastWriteTimeUtc != CapturedLastWriteTimeUtc;
    }

    internal static string NormalizeDestination(string path)
    {
        if (string.IsNullOrWhiteSpace(path)) throw new ArgumentException("A destination path is required.", nameof(path));
        var normalized = path.Trim().Replace('\\', '/').Trim('/');
        if (normalized.Length == 0 || normalized.Any(char.IsControl) || normalized.Contains(':') || normalized.Split('/').Any(part => part is "" or "." or ".." || part.Equals(".git", StringComparison.OrdinalIgnoreCase)))
            throw new ArgumentException("The destination must be a repository-relative file path.", nameof(path));
        return normalized;
    }
}

/// <summary>Creates a queue plan without accessing credentials or making network requests.</summary>
public static class UploadQueuePlanner
{
    private static readonly string[] DefaultExcludedDirectoryNames = { ".git", "bin", "obj", "node_modules" };

    public static IReadOnlyList<UploadQueueItem> FromFiles(IEnumerable<string> files, string destinationFolder = "")
    {
        ArgumentNullException.ThrowIfNull(files);
        var folder = string.IsNullOrWhiteSpace(destinationFolder) ? "" : destinationFolder.Trim().Replace('\\', '/').Trim('/');
        if (folder.Split('/').Any(part => part is "." or ".."))
            throw new ArgumentException("The destination folder cannot contain '.' or '..' segments.", nameof(destinationFolder));
        return files.Select(file =>
        {
            var name = Path.GetFileName(file);
            if (string.IsNullOrWhiteSpace(name)) throw new ArgumentException("A selected path must name a file.", nameof(files));
            return new UploadQueueItem(file, folder.Length == 0 ? name : folder + "/" + name);
        }).ToArray();
    }

    /// <summary>Traverses a folder recursively, preserving its relative directory structure.</summary>
    public static IReadOnlyList<UploadQueueItem> FromFolder(string folderPath, string destinationFolder = "", int maxFiles = 100,
        IEnumerable<string>? exclusionPatterns = null, int maxEntries = 50_000)
    {
        if (maxFiles is < 1 or > 10_000) throw new ArgumentOutOfRangeException(nameof(maxFiles), "The folder traversal limit must be between 1 and 10,000 files.");
        if (maxEntries is < 1 or > 1_000_000) throw new ArgumentOutOfRangeException(nameof(maxEntries), "The folder traversal entry limit must be between 1 and 1,000,000 entries.");
        var root = Path.GetFullPath(folderPath);
        if (!Directory.Exists(root)) throw new DirectoryNotFoundException(root);
        if ((File.GetAttributes(root) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidOperationException("Choose a real folder rather than a junction or symbolic link.");
        var files = new List<UploadQueueItem>();
        var pending = new Stack<string>();
        var rules = new TraversalExclusions(exclusionPatterns);
        var visitedEntries = 0;
        pending.Push(root);
        while (pending.Count > 0)
        {
            var current = pending.Pop();
            IEnumerable<string> children;
            try { children = Directory.EnumerateFileSystemEntries(current); }
            catch (Exception ex) when (IsTraversalAccessError(ex)) { continue; }

            IEnumerator<string> enumerator;
            try { enumerator = children.GetEnumerator(); }
            catch (Exception ex) when (IsTraversalAccessError(ex)) { continue; }
            using (enumerator)
            {
                while (true)
                {
                    string entry;
                    try { if (!enumerator.MoveNext()) break; entry = enumerator.Current; }
                    catch (Exception ex) when (IsTraversalAccessError(ex)) { break; }
                    if (++visitedEntries > maxEntries)
                        throw new InvalidOperationException($"Folder traversal stopped after examining {maxEntries} entries. Choose a smaller folder or increase the traversal limit.");

                    FileAttributes attributes;
                    try { attributes = File.GetAttributes(entry); }
                    catch (Exception ex) when (IsTraversalAccessError(ex)) { continue; }
                    if ((attributes & FileAttributes.ReparsePoint) != 0) continue;

                    var relative = Path.GetRelativePath(root, entry).Replace('\\', '/');
                    if ((attributes & FileAttributes.Directory) != 0)
                    {
                        if (!rules.IsExcludedDirectory(relative) || rules.MayReincludeDescendant(relative)) pending.Push(entry);
                        continue;
                    }

                    if (rules.IsExcludedFile(relative)) continue;
                    if (files.Count >= maxFiles) throw new InvalidOperationException($"This folder contains more than {maxFiles} files. Choose a smaller folder.");
                    var target = string.IsNullOrWhiteSpace(destinationFolder)
                        ? relative
                        : destinationFolder.Trim().Replace('\\', '/').TrimEnd('/') + "/" + relative;
                    try { files.Add(new UploadQueueItem(entry, target)); }
                    catch (Exception ex) when (IsTraversalAccessError(ex)) { /* The file disappeared or became inaccessible during enumeration. */ }
                }
            }
        }
        return files.OrderBy(item => item.DestinationPath, StringComparer.OrdinalIgnoreCase).ToArray();
    }

    private static bool IsTraversalAccessError(Exception ex) => ex is UnauthorizedAccessException or IOException or System.Security.SecurityException;

    /// <summary>Gitignore-like path exclusions used only for local folder discovery.</summary>
    private sealed class TraversalExclusions
    {
        private readonly Rule[] _rules;
        public TraversalExclusions(IEnumerable<string>? patterns)
        {
            _rules = (patterns ?? Array.Empty<string>())
                .Where(value => !string.IsNullOrWhiteSpace(value))
                .Select(value => value.Trim())
                .Where(value => !value.StartsWith('#'))
                .Select(value => new Rule(value))
                .ToArray();
        }

        public bool IsExcludedDirectory(string relativePath)
        {
            var segments = relativePath.Split('/');
            if (segments.Any(segment => DefaultExcludedDirectoryNames.Contains(segment, StringComparer.OrdinalIgnoreCase))) return true;
            return IsExcludedByRules(relativePath, isDirectory: true);
        }

        public bool IsExcludedFile(string relativePath) => IsExcludedByRules(relativePath, isDirectory: false);

        public bool MayReincludeDescendant(string relativeDirectory)
        {
            // Negated rules can rescue a nested path, so conservatively descend excluded user-pattern
            // directories when any negation exists. Built-in generated directories remain pruned.
            var segments = relativeDirectory.Split('/');
            if (segments.Any(segment => DefaultExcludedDirectoryNames.Contains(segment, StringComparer.OrdinalIgnoreCase))) return false;
            return _rules.Any(rule => rule.Negated && rule.MayMatchBelow(relativeDirectory));
        }

        private bool IsExcludedByRules(string relativePath, bool isDirectory)
        {
            var excluded = false;
            var pathSegments = relativePath.Split('/');
            for (var count = 1; count <= pathSegments.Length; count++)
            {
                var prefix = string.Join('/', pathSegments.Take(count));
                var prefixIsDirectory = count < pathSegments.Length || isDirectory;
                foreach (var rule in _rules)
                {
                    if (!rule.Matches(prefix, prefixIsDirectory)) continue;
                    excluded = !rule.Negated;
                }
            }
            return excluded;
        }

        private sealed class Rule
        {
            private readonly Regex _regex;
            private readonly bool _directoryOnly;
            private readonly string _staticPrefix;
            private readonly bool _matchesAnySegment;
            public Rule(string value)
            {
                Negated = value.StartsWith('!');
                if (Negated) value = value[1..];
                value = value.Replace('\\', '/');
                _directoryOnly = value.EndsWith('/');
                var anchored = value.StartsWith('/');
                value = value.TrimStart('/');
                value = value.TrimEnd('/');
                var hasSlash = value.Contains('/');
                _matchesAnySegment = !hasSlash;
                var wildcard = value.IndexOfAny(new[] { '*', '?' });
                _staticPrefix = wildcard < 0 ? value : value[..wildcard];
                var expression = GlobToRegex(value);
                if (!anchored && !hasSlash) expression = "(?:^|.*/)" + expression;
                _regex = new Regex("^" + expression + "$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant,
                    TimeSpan.FromMilliseconds(100));
            }
            public bool Negated { get; }
            public bool Matches(string relativePath, bool isDirectory) => (!_directoryOnly || isDirectory)
                && (_regex.IsMatch(relativePath) || (isDirectory && _regex.IsMatch(relativePath + "/")));
            public bool MayMatchBelow(string relativeDirectory)
            {
                if (_matchesAnySegment || _staticPrefix.Length == 0) return true;
                return _staticPrefix.StartsWith(relativeDirectory + "/", StringComparison.OrdinalIgnoreCase)
                    || relativeDirectory.StartsWith(_staticPrefix.TrimEnd('/'), StringComparison.OrdinalIgnoreCase)
                    || _regex.IsMatch(relativeDirectory);
            }

            private static string GlobToRegex(string pattern)
            {
                var result = new System.Text.StringBuilder();
                for (var i = 0; i < pattern.Length; i++)
                {
                    if (pattern[i] == '*')
                    {
                        if (i + 1 < pattern.Length && pattern[i + 1] == '*')
                        {
                            i++;
                            if (i + 1 < pattern.Length && pattern[i + 1] == '/') { i++; result.Append("(?:.*/)?"); }
                            else result.Append(".*");
                        }
                        else result.Append("[^/]*");
                    }
                    else if (pattern[i] == '?') result.Append("[^/]");
                    else result.Append(Regex.Escape(pattern[i].ToString()));
                }
                return result.ToString();
            }
        }
    }

    /// <summary>
    /// Resolves existing remote paths and duplicate destinations within the batch.
    /// Path comparisons follow GitHub's case-sensitive repository paths.
    /// </summary>
    public static IReadOnlyList<UploadQueueItem> ApplyCollisionPolicy(
        IEnumerable<UploadQueueItem> source,
        IEnumerable<string>? existingDestinationPaths,
        UploadCollisionPolicy policy)
    {
        ArgumentNullException.ThrowIfNull(source);
        var occupied = new HashSet<string>(StringComparer.Ordinal);
        if (existingDestinationPaths != null)
            foreach (var path in existingDestinationPaths) occupied.Add(UploadQueueItem.NormalizeDestination(path));

        var result = new List<UploadQueueItem>();
        foreach (var original in source)
        {
            var item = new UploadQueueItem(original.SourcePath, original.DestinationPath);
            if (occupied.Add(item.DestinationPath))
            {
                result.Add(item);
                continue;
            }

            switch (policy)
            {
                case UploadCollisionPolicy.Skip:
                    item.State = UploadQueueItemState.Skipped;
                    item.Error = "A file already exists at this destination.";
                    break;
                case UploadCollisionPolicy.Replace:
                    // Keep the path; subsequent same-batch duplicates will be treated as collisions.
                    break;
                case UploadCollisionPolicy.Rename:
                    var directory = Path.GetDirectoryName(item.DestinationPath.Replace('/', Path.DirectorySeparatorChar))?
                        .Replace(Path.DirectorySeparatorChar, '/') ?? "";
                    var name = Path.GetFileName(item.DestinationPath);
                    var stem = Path.GetFileNameWithoutExtension(name);
                    var extension = Path.GetExtension(name);
                    var suffix = 2;
                    string renamed;
                    do
                    {
                        var candidateName = $"{stem} ({suffix++}){extension}";
                        renamed = directory.Length == 0 ? candidateName : directory + "/" + candidateName;
                    } while (!occupied.Add(renamed));
                    item.DestinationPath = renamed;
                    break;
                default:
                    throw new ArgumentOutOfRangeException(nameof(policy));
            }
            result.Add(item);
        }
        return result;
    }
}

/// <summary>
/// Sequential queue orchestration. A host supplies the upload delegate; this class has no
/// credentials or network behavior. Pausing takes effect between items, cancellation is immediate.
/// </summary>
public sealed class UploadQueueService
{
    private readonly object _sync = new();
    private readonly List<UploadQueueItem> _items;
    private CancellationTokenSource? _runCancellation;
    private TaskCompletionSource<bool>? _resumeSignal;
    private bool _isRunning;
    private bool _pauseRequested;

    public UploadQueueService(IEnumerable<UploadQueueItem> items)
    {
        ArgumentNullException.ThrowIfNull(items);
        _items = items.ToList();
    }

    public event EventHandler? Changed;
    public IReadOnlyList<UploadQueueItem> Items { get { lock (_sync) return _items.ToArray(); } }
    public bool IsRunning { get { lock (_sync) return _isRunning; } }
    public bool IsPaused { get { lock (_sync) return _isRunning && _pauseRequested; } }

    public async Task RunAsync(
        Func<UploadQueueItem, IProgress<double>, CancellationToken, Task> executor,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(executor);
        CancellationTokenSource runCts;
        lock (_sync)
        {
            if (_isRunning) throw new InvalidOperationException("The upload queue is already running.");
            _isRunning = true;
            _pauseRequested = false;
            _runCancellation = runCts = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        }
        RaiseChanged();
        try
        {
            foreach (var item in Items)
            {
                await WaitUntilResumedAsync(runCts.Token).ConfigureAwait(false);
                runCts.Token.ThrowIfCancellationRequested();
                if (item.State is not (UploadQueueItemState.Queued or UploadQueueItemState.Failed)) continue;

                if (item.HasChangedOnDisk())
                {
                    item.State = UploadQueueItemState.Failed;
                    item.Error = "The local file changed after it was added. Add it again to upload the current version.";
                    RaiseChanged();
                    continue;
                }

                item.State = UploadQueueItemState.Running;
                item.Error = null;
                item.ProgressPercent = 0;
                RaiseChanged();
                var progress = new InlineProgress(value =>
                {
                    item.ProgressPercent = Math.Clamp(value, 0, 100);
                    RaiseChanged();
                });
                try
                {
                    await executor(item, progress, runCts.Token).ConfigureAwait(false);
                    item.ProgressPercent = 100;
                    item.State = UploadQueueItemState.Succeeded;
                }
                catch (OperationCanceledException) when (runCts.IsCancellationRequested)
                {
                    item.State = UploadQueueItemState.Cancelled;
                    item.Error = "Cancelled.";
                    throw;
                }
                catch (Exception ex)
                {
                    item.State = UploadQueueItemState.Failed;
                    item.Error = ex.Message;
                }
                RaiseChanged();
            }
        }
        catch (OperationCanceledException) when (runCts.IsCancellationRequested)
        {
            foreach (var item in Items.Where(item => item.State == UploadQueueItemState.Queued))
            {
                item.State = UploadQueueItemState.Cancelled;
                item.Error = "Cancelled before upload.";
            }
            RaiseChanged();
        }
        finally
        {
            lock (_sync)
            {
                _isRunning = false;
                _pauseRequested = false;
                _resumeSignal?.TrySetResult(true);
                _resumeSignal = null;
                _runCancellation = null;
            }
            runCts.Dispose();
            RaiseChanged();
        }
    }

    /// <summary>Pauses after the currently executing file completes.</summary>
    public void Pause()
    {
        lock (_sync)
        {
            if (!_isRunning || _pauseRequested) return;
            _pauseRequested = true;
            _resumeSignal = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        }
        RaiseChanged();
    }

    public void Resume()
    {
        lock (_sync)
        {
            if (!_pauseRequested) return;
            _pauseRequested = false;
            _resumeSignal?.TrySetResult(true);
            _resumeSignal = null;
        }
        RaiseChanged();
    }

    public void Cancel()
    {
        lock (_sync) _runCancellation?.Cancel();
    }

    /// <summary>Resets failed/cancelled items so the host can run the queue again.</summary>
    public void RetryFailed()
    {
        lock (_sync)
        {
            if (_isRunning) throw new InvalidOperationException("Stop the queue before retrying failed items.");
            foreach (var item in _items.Where(item => item.State is UploadQueueItemState.Failed or UploadQueueItemState.Cancelled))
            {
                item.State = UploadQueueItemState.Queued;
                item.ProgressPercent = 0;
                item.Error = null;
            }
        }
        RaiseChanged();
    }

    private async Task WaitUntilResumedAsync(CancellationToken cancellationToken)
    {
        Task? waitTask;
        lock (_sync) waitTask = _pauseRequested ? _resumeSignal?.Task : null;
        if (waitTask != null) await waitTask.WaitAsync(cancellationToken).ConfigureAwait(false);
    }

    private void RaiseChanged()
    {
        var handlers = Changed;
        if (handlers == null) return;
        foreach (EventHandler handler in handlers.GetInvocationList())
        {
            try { handler(this, EventArgs.Empty); } catch { /* UI observers must not break queue execution. */ }
        }
    }

    private sealed class InlineProgress : IProgress<double>
    {
        private readonly Action<double> _report;
        public InlineProgress(Action<double> report) => _report = report;
        public void Report(double value) => _report(value);
    }
}
