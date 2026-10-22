using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Threading;

namespace FileToGitHub;

public sealed class BatchUploadFile
{
    public BatchUploadFile(string sourcePath, string destinationPath, string commitMessage, long size, DateTime? capturedLastWriteTimeUtc = null)
    { SourcePath = sourcePath; DestinationPath = destinationPath; CommitMessage = commitMessage; Size = size; CapturedLastWriteTimeUtc = capturedLastWriteTimeUtc; }
    public string SourcePath { get; }
    public string DestinationPath { get; }
    public string CommitMessage { get; }
    public long Size { get; }
    public DateTime? CapturedLastWriteTimeUtc { get; }
}

public sealed class BatchUploadResult
{
    public BatchUploadResult(string sourcePath, bool succeeded, string? url = null, string? error = null)
    { SourcePath = sourcePath; Succeeded = succeeded; Url = url; Error = error; }
    public string SourcePath { get; }
    public bool Succeeded { get; }
    public string? Url { get; }
    public string? Error { get; }
}

public sealed class BatchUploadProgress
{
    public BatchUploadProgress(string sourcePath, double percent) { SourcePath = sourcePath; Percent = Math.Clamp(percent, 0, 100); }
    public string SourcePath { get; }
    public double Percent { get; }
}

/// <summary>Checks that a queued local source is still the reviewed file and can be opened for upload.</summary>
public static class BatchUploadSourceReadiness
{
    public static bool TryValidate(string path, long expectedLength, DateTime? expectedLastWriteTimeUtc, out string? error)
    {
        error = null;
        try
        {
            // Keep this probe read-only. FileShare.Read rejects an existing exclusive lock and
            // prevents cooperating writers/deleters from changing the source during the probe.
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 4096, FileOptions.SequentialScan);
            var lastWriteUtc = File.GetLastWriteTimeUtc(path);
            if (stream.Length != expectedLength || (expectedLastWriteTimeUtc.HasValue && lastWriteUtc != expectedLastWriteTimeUtc.Value))
            {
                error = "The source changed after it was queued. Review it again before uploading.";
                return false;
            }
            return true;
        }
        catch (FileNotFoundException) { error = "The source file is missing. Restore it and retry, or skip it."; }
        catch (DirectoryNotFoundException) { error = "The source folder is missing. Restore it and retry, or skip it."; }
        catch (UnauthorizedAccessException) { error = "Windows denied access to this file. Close the app holding it or fix access, then retry, or skip it."; }
        catch (IOException ex) { error = "The file is unavailable or locked by another app. Close that app, then retry, or skip it. " + ex.Message; }
        catch (ArgumentException ex) { error = "The source path is invalid. Add the file again. " + ex.Message; }
        return false;
    }
}

public enum BatchCommitMode { PerFile, SingleBatch }

public sealed class BatchUploadEntry : System.ComponentModel.INotifyPropertyChanged
{
    private string _destinationPath;
    private string _commitMessage;
    internal BatchUploadEntry(UploadQueueItem item, string message)
    {
        Item = item; _destinationPath = item.DestinationPath; _commitMessage = message;
        var info = new FileInfo(item.SourcePath); Size = info.Exists ? info.Length : item.CapturedLength;
        StatusText = item.State == UploadQueueItemState.Skipped ? "Skipped" : "Ready";
        Error = item.Error;
    }
    internal UploadQueueItem Item { get; private set; }
    public string SourcePath => Item.SourcePath;
    public string DestinationPath { get => _destinationPath; set { if (_destinationPath != value) { _destinationPath = value; Item.DestinationPath = UploadQueueItem.NormalizeDestination(value); Changed(nameof(DestinationPath)); } } }
    public string CommitMessage { get => _commitMessage; set { _commitMessage = value ?? ""; Changed(nameof(CommitMessage)); } }
    public long Size { get; private set; }
    public string SizeText => Size < 1024 * 1024 ? $"{Size / 1024d:0.#} KB" : $"{Size / (1024d * 1024):0.##} MB";
    public string ProgressText { get; internal set; } = "—";
    public string StatusText { get; internal set; }
    public string? Error { get; internal set; }
    public string? Url { get; internal set; }
    public bool HasUrl => Uri.TryCreate(Url, UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps && uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase);
    public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged;
    internal void Changed(string property) => PropertyChanged?.Invoke(this, new System.ComponentModel.PropertyChangedEventArgs(property));
    internal void RefreshSource()
    {
        var current = UploadQueuePlanner.FromFiles(new[] { SourcePath }).Single();
        Item = current; Size = current.CapturedLength; StatusText = "Ready"; Error = null; ProgressText = "—";
        Changed(nameof(Size)); Changed(nameof(SizeText)); Refresh();
    }
    internal void Refresh() { Changed(nameof(DestinationPath)); Changed(nameof(CommitMessage)); Changed(nameof(ProgressText)); Changed(nameof(StatusText)); Changed(nameof(Error)); Changed(nameof(Url)); Changed(nameof(HasUrl)); }
}

/// <summary>Review and execute an upload batch using only the host-provided callback.</summary>
public partial class BatchUploadWindow : Window
{
    public delegate Task<BatchUploadResult> SingleFileUpload(BatchUploadFile file, IProgress<double> progress, CancellationToken cancellationToken);
    public delegate Task<System.Collections.Generic.IReadOnlyList<BatchUploadResult>> SingleCommitUpload(
        System.Collections.Generic.IReadOnlyList<BatchUploadFile> files, string commitMessage,
        IProgress<BatchUploadProgress> progress, CancellationToken cancellationToken);

    private readonly ObservableCollection<BatchUploadEntry> _entries;
    private readonly string _repository;
    private readonly string _branch;
    private readonly string _defaultCommitMessage;
    private readonly SingleFileUpload _uploadOne;
    private readonly SingleCommitUpload? _uploadBatch;
    private readonly PersistentUploadQueueStore _queueStore = new();
    private readonly bool _persistQueue;
    private bool _recoveryLoaded;
    private bool _saveWarningShown;
    private CancellationTokenSource? _runCts;
    private bool _paused;
    private TaskCompletionSource<bool>? _resumeSignal;

    public BatchUploadWindow(System.Collections.Generic.IEnumerable<UploadQueueItem> items, string repository, string branch,
        string defaultCommitMessage, SingleFileUpload uploadOne, SingleCommitUpload? uploadBatch = null, string transferNotice = "", bool persistQueue = true)
    {
        UniformUi.Prepare(this);
        InitializeComponent();
        UniformUi.SetDestination(this, () => repository + "  /  " + branch);
        _persistQueue = persistQueue;
        _repository = repository ?? ""; _branch = branch ?? ""; _defaultCommitMessage = defaultCommitMessage ?? "Upload files";
        _uploadOne = uploadOne ?? throw new ArgumentNullException(nameof(uploadOne)); _uploadBatch = uploadBatch;
        _entries = new ObservableCollection<BatchUploadEntry>((items ?? throw new ArgumentNullException(nameof(items))).Select(item => new BatchUploadEntry(item, _defaultCommitMessage)));
        QueueGrid.ItemsSource = _entries;
        DestinationText.Text = $"{_repository} · {(_branch.Length == 0 ? "default branch" : _branch)}";
        NetworkNotice.Text = transferNotice;
        NetworkNotice.Visibility = string.IsNullOrWhiteSpace(transferNotice) ? Visibility.Collapsed : Visibility.Visible;
        CommitModeBox.SelectedIndex = _uploadBatch == null ? 0 : 1;
        BatchMessageBox.Text = _defaultCommitMessage;
        Loaded += RestoreQueue;
        Closing += (_, e) =>
        {
            if (_runCts != null) { e.Cancel = true; OctoShipDialog.Show(this, "Cancel the active upload and wait for it to finish before closing."); return; }
            SaveQueue();
        };
        UpdateSummary();
    }

    /// <summary>Final summary after the window closes; null means the user closed before starting.</summary>
    public System.Collections.Generic.IReadOnlyList<BatchUploadResult>? FinalResults { get; private set; }

    private BatchCommitMode CommitMode => CommitModeBox.SelectedIndex == 1 ? BatchCommitMode.SingleBatch : BatchCommitMode.PerFile;
    private void CommitModeBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (QueueGrid == null || StartButton == null) return;
        var one = CommitMode == BatchCommitMode.SingleBatch;
        if (BatchMessageBox != null) BatchMessageBox.IsEnabled = one;
        QueueGrid.Columns[3].IsReadOnly = one;
        if (one && _uploadBatch == null) { QueueGrid.Columns[3].Header = "Message (batch callback required)"; StartButton.IsEnabled = false; }
        else { QueueGrid.Columns[3].Header = one ? "Per-file messages ignored" : "Commit message"; StartButton.IsEnabled = true; }
    }
    private void CollisionBox_SelectionChanged(object sender, SelectionChangedEventArgs e) { }
    private bool MatchesFilter(BatchUploadEntry entry) => QueueFilterBox.SelectedIndex switch
    {
        1 => entry.StatusText == "Ready",
        2 => entry.StatusText == "Skipped",
        3 => entry.StatusText == "Uploaded",
        4 => entry.StatusText is "Failed" or "Cancelled" or "Uncertain" or "Changed",
        _ => true
    };
    private void QueueFilterBox_SelectionChanged(object sender, SelectionChangedEventArgs e) => ApplyQueueFilter();
    private void ApplyQueueFilter()
    {
        if (QueueGrid == null || _entries == null) return;
        var view = CollectionViewSource.GetDefaultView(_entries);
        view.Filter = item => item is BatchUploadEntry entry && MatchesFilter(entry);
        view.Refresh();
    }
    private void SelectByRule_Click(object sender, RoutedEventArgs e)
    {
        var pattern = SelectPatternBox.Text.Trim();
        if (pattern.Length == 0) { OctoShipDialog.Show(this, "Enter a path or glob pattern, such as docs/** or *.md."); return; }
        QueueGrid.SelectedItems.Clear();
        foreach (var entry in _entries.Where(x => MatchesPattern(x.SourcePath, pattern) || MatchesPattern(x.DestinationPath, pattern)))
            QueueGrid.SelectedItems.Add(entry);
        if (QueueGrid.SelectedItems.Count == 0) OctoShipDialog.Show(this, "No queued files match that pattern.", "Select files", MessageBoxButton.OK, MessageBoxImage.Information);
    }
    private void DestinationTree_Click(object sender, RoutedEventArgs e) => OctoShipDialog.Show(this, BuildDestinationTree(_entries), "Planned repository paths", MessageBoxButton.OK, MessageBoxImage.Information);
    private static string BuildDestinationTree(IEnumerable<BatchUploadEntry> entries)
    {
        var root = new SortedDictionary<string, object>(StringComparer.Ordinal);
        foreach (var entry in entries)
        {
            var node = root;
            var parts = entry.DestinationPath.Split('/');
            for (var i = 0; i < parts.Length - 1; i++)
            {
                if (!node.TryGetValue(parts[i], out var child)) node[parts[i]] = child = new SortedDictionary<string, object>(StringComparer.Ordinal);
                if (child is not SortedDictionary<string, object> next) break;
                node = next;
            }
            if (parts.Length > 0) node[parts[^1]] = null!;
        }
        var lines = new System.Collections.Generic.List<string>();
        void Add(SortedDictionary<string, object> tree, int depth)
        {
            foreach (var pair in tree)
            {
                lines.Add(new string(' ', depth * 2) + pair.Key + (pair.Value is SortedDictionary<string, object> ? "/" : ""));
                if (pair.Value is SortedDictionary<string, object> child) Add(child, depth + 1);
            }
        }
        Add(root, 0);
        var text = string.Join("\n", lines);
        return text.Length == 0 ? "No destination paths are queued." : text.Length > 12000 ? text[..12000] + "\n… (tree truncated)" : text;
    }
    private void QueueGrid_CellEditEnding(object sender, DataGridCellEditEndingEventArgs e) => Dispatcher.BeginInvoke(new Action(UpdateSummary));
    private void AddFiles_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Multiselect = true, Title = "Add files to upload" };
        if (dialog.ShowDialog(this) != true) return;
        foreach (var item in UploadQueuePlanner.FromFiles(dialog.FileNames))
        {
            var entry = new BatchUploadEntry(item, _defaultCommitMessage);
            if (_entries.Any(x => x.SourcePath.Equals(entry.SourcePath, StringComparison.OrdinalIgnoreCase))) continue;
            if (_entries.Count >= 100) { OctoShipDialog.Show(this, "A batch supports at most 100 files."); break; }
            _entries.Add(entry);
        }
        ApplyRules(); UpdateSummary();
    }
    private void Remove_Click(object sender, RoutedEventArgs e)
    {
        foreach (BatchUploadEntry row in QueueGrid.SelectedItems.Cast<object>().OfType<BatchUploadEntry>().ToArray())
            if (row.StatusText is "Ready" or "Skipped" or "Failed") _entries.Remove(row);
        UpdateSummary();
    }
    private void MoveUp_Click(object sender, RoutedEventArgs e) => MoveSelected(-1);
    private void MoveDown_Click(object sender, RoutedEventArgs e) => MoveSelected(1);
    private void MoveSelected(int offset)
    {
        var selected = QueueGrid.SelectedItems.Cast<object>().OfType<BatchUploadEntry>().ToList();
        if (selected.Count != 1) return;
        var index = _entries.IndexOf(selected[0]); var next = Math.Clamp(index + offset, 0, _entries.Count - 1);
        if (index == next) return;
        if (selected[0].StatusText != "Ready" || _entries[next].StatusText != "Ready")
        {
            OctoShipDialog.Show(this, "Reorder only adjacent ready items. Uploaded, skipped, failed, changed, and uncertain items keep their relative position until resolved.", "Safe queue ordering", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        _entries.Move(index, next); QueueGrid.SelectedItem = selected[0]; SaveQueue();
    }
    private void ApplyRules_Click(object sender, RoutedEventArgs e) { ApplyRules(); UpdateSummary(); }
    private bool ApplyRules()
    {
        var maxMB = 50d;
        if (!double.TryParse(MaxSizeBox.Text, out maxMB) || !double.IsFinite(maxMB) || maxMB <= 0 || maxMB > 50) { OctoShipDialog.Show(this, "Enter a maximum size greater than zero and at most 50 MiB.", "Invalid size", MessageBoxButton.OK, MessageBoxImage.Warning); return false; }
        var patterns = IgnoreBox.Text.Split(new[] { ',', ';', '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).Select(x => x.Trim()).Where(x => x.Length > 0).ToArray();
        foreach (var entry in _entries)
        {
            if (entry.StatusText is "Uploaded" or "Uploading" or "Uncertain" or "Changed") continue;
            if (entry.Size > maxMB * 1024 * 1024) { entry.StatusText = "Skipped"; entry.Error = $"Exceeds {maxMB:0.##} MB limit."; }
            else if (patterns.Any(pattern => MatchesPattern(entry.SourcePath, pattern) || MatchesPattern(entry.DestinationPath, pattern))) { entry.StatusText = "Skipped"; entry.Error = "Matched an ignore pattern."; }
            else { entry.StatusText = "Ready"; entry.Error = null; }
            entry.Refresh();
        }
        // Resolve collisions within this batch. Remote collisions require host preflight and are not inferred here.
        var seen = new System.Collections.Generic.HashSet<string>(StringComparer.Ordinal);
        foreach (var entry in _entries.Where(x => x.StatusText == "Ready"))
        {
            if (seen.Add(entry.DestinationPath)) continue;
            if (CollisionBox.SelectedIndex == 1) { entry.StatusText = "Skipped"; entry.Error = "Another queued file uses this destination."; }
            else
            {
                var path = entry.DestinationPath; var dir = Path.GetDirectoryName(path.Replace('/', Path.DirectorySeparatorChar))?.Replace(Path.DirectorySeparatorChar, '/') ?? "";
                var name = Path.GetFileName(path); var stem = Path.GetFileNameWithoutExtension(name); var ext = Path.GetExtension(name); var n = 2; string candidate;
                do { var leaf = $"{stem} ({n++}){ext}"; candidate = dir.Length == 0 ? leaf : dir + "/" + leaf; } while (!seen.Add(candidate));
                entry.DestinationPath = candidate;
            }
            entry.Refresh();
        }
        return true;
    }
    private static bool MatchesPattern(string value, string pattern)
    {
        var normalized = value.Replace('\\', '/'); var p = pattern.Replace('\\', '/');
        var expression = "^" + Regex.Escape(p).Replace("\\*\\*", ".*").Replace("\\*", "[^/]*").Replace("\\?", "[^/]") + "$";
        var leaf = normalized.Split('/').Last();
        return Regex.IsMatch(normalized, expression, RegexOptions.IgnoreCase | RegexOptions.CultureInvariant) ||
               (!p.Contains('/') && Regex.IsMatch(leaf, expression, RegexOptions.IgnoreCase | RegexOptions.CultureInvariant));
    }
    private async void Start_Click(object sender, RoutedEventArgs e)
    {
        if (!QueueGrid.CommitEdit(DataGridEditingUnit.Cell, true) || !QueueGrid.CommitEdit(DataGridEditingUnit.Row, true)) return;
        if (!ApplyRules()) return;
        var candidates = _entries.Where(x => x.StatusText is "Ready" or "Failed").ToArray();
        foreach (var entry in candidates)
        {
            if (!BatchUploadSourceReadiness.TryValidate(entry.SourcePath, entry.Item.CapturedLength, entry.Item.CapturedLastWriteTimeUtc, out var sourceError))
            {
                entry.StatusText = sourceError?.Contains("changed after it was queued", StringComparison.OrdinalIgnoreCase) == true ? "Changed" : "Failed";
                entry.Error = sourceError; entry.ProgressText = "—"; entry.Refresh();
            }
            else { entry.StatusText = "Ready"; entry.Error = null; entry.Refresh(); }
        }
        UpdateSummary();
        var ready = candidates.Where(x => x.StatusText == "Ready").ToArray();
        var blocked = _entries.Where(x => x.StatusText is "Changed" or "Uncertain" or "Failed").ToArray();
        if (blocked.Length > 0)
        {
            var details = string.Join("\n", blocked.Take(12).Select(x => $"• {Path.GetFileName(x.SourcePath)} — {x.Error ?? (x.StatusText == "Uncertain" ? "Check GitHub before retrying." : x.StatusText)}"));
            OctoShipDialog.Show(this, "Resolve these files before starting. Select a row to inspect its full details. Changed sources can be refreshed with Review changed source; uncertain uploads need a GitHub check before retry.\n\n" + details,
                "Preflight needs attention", MessageBoxButton.OK, MessageBoxImage.Warning);
            if (blocked.Length > 0) { QueueFilterBox.SelectedIndex = 4; QueueGrid.SelectedItem = blocked[0]; QueueGrid.ScrollIntoView(blocked[0]); }
            return;
        }
        if (ready.Length == 0) { OctoShipDialog.Show(this, "There are no ready files to upload.", "Upload", MessageBoxButton.OK, MessageBoxImage.Information); return; }
        if (ready.Length > 100) { OctoShipDialog.Show(this, "A batch supports at most 100 files."); return; }
        foreach (var entry in ready)
        {
            try { UploadQueueItem.NormalizeDestination(entry.DestinationPath); }
            catch (ArgumentException ex) { OctoShipDialog.Show(this, ex.Message); return; }
        }
        if ((CommitMode == BatchCommitMode.SingleBatch && string.IsNullOrWhiteSpace(BatchMessageBox.Text)) ||
            (CommitMode == BatchCommitMode.PerFile && ready.Any(x => string.IsNullOrWhiteSpace(x.CommitMessage))))
        { OctoShipDialog.Show(this, "Enter a commit message before uploading."); return; }
        var pathWarnings = UploadPathAudit.Analyze(ready.Select(x => x.DestinationPath));
        if (pathWarnings.Count > 0 && OctoShipDialog.Show(this,
            "Some destination paths may be interpreted differently across Windows and GitHub. Review these warnings before continuing:\n\n" +
            string.Join("\n", pathWarnings) + "\n\nContinue with the exact paths shown in the queue?",
            "Destination path review", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
        var totalBytes = ready.Sum(x => x.Size);
        var plan = string.Join("\n", ready.Take(20).Select(x => $"{x.DestinationPath}  ←  {Path.GetFileName(x.SourcePath)}"));
        if (ready.Length > 20) plan += $"\n… and {ready.Length - 20} more file(s)";
        var dryRun = $"DRY RUN — no files have been sent.\n\nRepository: {_repository}\nBranch: {_branch}\nFiles: {ready.Length}\nTotal: {FormatBytes(totalBytes)}\nCommit mode: {(CommitMode == BatchCommitMode.SingleBatch ? "one commit" : "one commit per file")}\n\n{plan}\n\nSkipped: {_entries.Count(x => x.StatusText == "Skipped")}. Existing destinations are checked again immediately before upload.";
        if (OctoShipDialog.Show(this, dryRun + "\n\nProceed with this reviewed plan?", "Dry run and shipment review", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
        _runCts = new CancellationTokenSource(); SetRunning(true);
        try
        {
            if (CommitMode == BatchCommitMode.SingleBatch) await RunSingleBatchAsync(ready, _runCts.Token);
            else await RunPerFileAsync(ready, _runCts.Token);
        }
        catch (OperationCanceledException)
        {
            foreach (var entry in ready.Where(x => x.StatusText is "Ready" or "Uploading")) { entry.StatusText = "Cancelled"; entry.Error = "Cancelled. Check GitHub before retrying."; entry.Refresh(); }
        }
        catch (Exception ex) { OctoShipDialog.Show(this, ex.Message, "Batch upload failed"); }
        finally { _runCts.Dispose(); _runCts = null; SetRunning(false); SaveQueue(); }
        FinalResults = _entries.Select(x => new BatchUploadResult(x.SourcePath, x.StatusText == "Uploaded", x.Url, x.Error)).ToArray();
        var ok = FinalResults.Count(x => x.Succeeded); var skipped = _entries.Count(x => x.StatusText == "Skipped"); var failed = FinalResults.Count(x => !x.Succeeded) - skipped;
        var receipt = string.Join("\n", _entries.Select(x => $"{x.StatusText}: {x.DestinationPath}" + (x.Url is not null ? $"\n  {x.Url}" : x.Error is not null ? $"\n  {x.Error}" : "")));
        if (receipt.Length > 12000) receipt = receipt[..12000] + "\n… (receipt truncated)";
        OctoShipDialog.Show(this, $"Shipment receipt\n\nRepository: {_repository}\nBranch: {_branch}\nUploaded: {ok}  ·  Skipped: {skipped}  ·  Failed or uncertain: {Math.Max(0, failed)}\n\n{receipt}", "Shipment receipt", MessageBoxButton.OK, ok == ready.Length ? MessageBoxImage.Information : MessageBoxImage.Warning);
    }
    private async Task RunPerFileAsync(BatchUploadEntry[] entries, CancellationToken token)
    {
        var sw = Stopwatch.StartNew(); long sent = 0; var processed = 0;
        foreach (var entry in entries)
        {
            if (_paused && _resumeSignal != null) await _resumeSignal.Task.WaitAsync(token);
            if (token.IsCancellationRequested) { entry.StatusText = "Cancelled"; entry.Error = "Cancelled before upload."; entry.Refresh(); continue; }
            entry.StatusText = "Uploading"; entry.ProgressText = "0%"; entry.Refresh(); SaveQueue();
            if (!BatchUploadSourceReadiness.TryValidate(entry.SourcePath, entry.Item.CapturedLength, entry.Item.CapturedLastWriteTimeUtc, out var sourceError))
            {
                entry.StatusText = "Failed"; entry.Error = sourceError; entry.ProgressText = "—"; entry.Refresh(); processed++; UpdateSummary(); continue;
            }
            var file = new BatchUploadFile(entry.SourcePath, entry.DestinationPath, entry.CommitMessage, entry.Item.CapturedLength, entry.Item.CapturedLastWriteTimeUtc);
            var progress = new Progress<double>(value => { entry.ProgressText = $"{Math.Clamp(value, 0, 100):0}%"; OverallProgress.Value = Math.Clamp((processed + value / 100d) / entries.Length * 100, 0, 100); ProgressText.Text = Estimate(sw.Elapsed, sent + (long)(entry.Size * Math.Clamp(value, 0, 100) / 100d), entries.Sum(x => x.Size)); entry.Refresh(); });
            try
            {
                var result = await _uploadOne(file, progress, token); entry.Url = result.Url;
                entry.StatusText = result.Succeeded ? "Uploaded" : "Failed"; entry.Error = result.Error; entry.ProgressText = result.Succeeded ? "100%" : entry.ProgressText;
                if (result.Succeeded) sent += entry.Size;
            }
            catch (OperationCanceledException) when (!token.IsCancellationRequested) { entry.StatusText = "Failed"; entry.Error = "Upload was declined or cancelled before the request completed."; }
            catch (OperationCanceledException) { entry.StatusText = "Uncertain"; entry.Error = "The upload was interrupted after it started. Check the destination on GitHub before retrying."; }
            catch (Exception ex) { entry.StatusText = "Uncertain"; entry.Error = "The request may have reached GitHub. Check the destination on GitHub before retrying. " + ex.Message; }
            processed++; entry.Refresh(); UpdateSummary();
        }
    }
    private async Task RunSingleBatchAsync(BatchUploadEntry[] entries, CancellationToken token)
    {
        if (_uploadBatch == null) throw new InvalidOperationException("The host did not provide a single-commit upload callback.");
        foreach (var entry in entries)
        {
            if (!BatchUploadSourceReadiness.TryValidate(entry.SourcePath, entry.Item.CapturedLength, entry.Item.CapturedLastWriteTimeUtc, out var sourceError))
            {
                entry.StatusText = "Failed"; entry.Error = sourceError; entry.ProgressText = "—"; entry.Refresh();
            }
        }
        if (entries.Any(x => x.StatusText == "Failed"))
        {
            foreach (var entry in entries.Where(x => x.StatusText != "Failed")) { entry.StatusText = "Ready"; entry.Refresh(); }
            OctoShipDialog.Show(this, "At least one source file is unavailable or changed. No batch commit was sent. Close apps holding the file, then choose Retry failed, or remove/skip that entry and start again.", "Batch source recovery", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        var files = entries.Select(x => new BatchUploadFile(x.SourcePath, x.DestinationPath, x.CommitMessage, x.Item.CapturedLength, x.Item.CapturedLastWriteTimeUtc)).ToArray();
        foreach (var entry in entries) { entry.StatusText = "Uploading"; entry.ProgressText = "0%"; entry.Refresh(); }
        SaveQueue();
        var last = new System.Collections.Generic.Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        var sw = Stopwatch.StartNew();
        var progress = new Progress<BatchUploadProgress>(p =>
        {
            var entry = entries.FirstOrDefault(x => x.SourcePath.Equals(p.SourcePath, StringComparison.OrdinalIgnoreCase));
            if (entry != null) { last[p.SourcePath] = p.Percent; entry.ProgressText = $"{p.Percent:0}%"; entry.Refresh(); }
            var aggregate = entries.Average(x => last.TryGetValue(x.SourcePath, out var v) ? v : 0);
            OverallProgress.Value = aggregate; ProgressText.Text = $"{aggregate:0}% · {sw.Elapsed:mm\\:ss}";
        });
        try
        {
            var results = await _uploadBatch(files, BatchMessageBox.Text.Trim(), progress, token);
            foreach (var entry in entries)
            {
                var result = results.FirstOrDefault(x => x.SourcePath.Equals(entry.SourcePath, StringComparison.OrdinalIgnoreCase));
                entry.StatusText = result?.Succeeded == true ? "Uploaded" : result == null ? "Uncertain" : "Failed";
                entry.Url = result?.Url;
                entry.Error = result?.Error ?? (result == null ? "No result was returned for this file. The batch may have published it; check GitHub before retrying." : null);
                entry.ProgressText = result?.Succeeded == true ? "100%" : entry.ProgressText; entry.Refresh();
            }
        }
        catch (Exception ex) { foreach (var entry in entries) { entry.StatusText = "Uncertain"; entry.Error = "The batch request may have reached GitHub. Check all destinations on GitHub before retrying. " + ex.Message; entry.Refresh(); } }
        OverallProgress.Value = entries.Count(x => x.StatusText == "Uploaded") * 100d / entries.Length; UpdateSummary();
    }
    private void Retry_Click(object sender, RoutedEventArgs e)
    {
        var selected = QueueGrid.SelectedItems.Cast<object>().OfType<BatchUploadEntry>().Where(x => x.StatusText is "Failed" or "Cancelled" or "Uncertain").ToArray();
        var retry = selected.Length > 0 ? selected : _entries.Where(x => x.StatusText is "Failed" or "Cancelled" or "Uncertain").ToArray();
        if (retry.Any(x => x.StatusText == "Uncertain") && OctoShipDialog.Show(this,
            "Some requests may already have published. Check each destination on GitHub first. Retry only files you confirmed are still missing.",
            "Resolve uncertain uploads", MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK) return;
        foreach (var entry in retry) { entry.StatusText = "Ready"; entry.Error = null; entry.ProgressText = "—"; entry.Refresh(); }
        StartButton.IsEnabled = true; RetryButton.IsEnabled = false; UpdateSummary();
    }
    private void RefreshSource_Click(object sender, RoutedEventArgs e)
    {
        var selected = QueueGrid.SelectedItems.Cast<object>().OfType<BatchUploadEntry>().Where(x => x.StatusText == "Changed").ToArray();
        var targets = selected.Length > 0 ? selected : _entries.Where(x => x.StatusText == "Changed").ToArray();
        foreach (var entry in targets)
        {
            try { entry.RefreshSource(); }
            catch (Exception ex) { entry.StatusText = "Failed"; entry.Error = "Could not review current source: " + ex.Message; entry.Refresh(); }
        }
        UpdateSummary();
    }
    private void Pause_Click(object sender, RoutedEventArgs e)
    {
        _paused = !_paused;
        if (_paused) { _resumeSignal = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously); PauseButton.Content = "Resume"; }
        else { _resumeSignal?.TrySetResult(true); _resumeSignal = null; PauseButton.Content = "Pause"; }
    }
    private void Cancel_Click(object sender, RoutedEventArgs e) => _runCts?.Cancel();
    private void Close_Click(object sender, RoutedEventArgs e) { if (_runCts != null) { OctoShipDialog.Show(this, "Cancel the active upload before closing."); return; } Close(); }
    private void OpenLink_Click(object sender, RoutedEventArgs e) { if ((sender as Button)?.Tag is string url && Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme == "https" && uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase)) TrustedProcess.Start(new ProcessStartInfo(uri.ToString()) { UseShellExecute = true }); }
    private void SetRunning(bool running)
    {
        QueueGrid.IsReadOnly = running;
        CommitModeBox.IsEnabled = CollisionBox.IsEnabled = MaxSizeBox.IsEnabled = IgnoreBox.IsEnabled = ApplyRulesButton.IsEnabled = !running;
        BatchMessageBox.IsEnabled = !running && CommitMode == BatchCommitMode.SingleBatch;
        StartButton.IsEnabled = !running && (CommitMode != BatchCommitMode.SingleBatch || _uploadBatch != null);
        foreach (var control in new[] { RetryButton, RefreshSourceButton, AddFilesButtonControl, RemoveButtonControl, MoveUpButtonControl, MoveDownButtonControl, SelectByRuleButton, DestinationTreeButton }) control.IsEnabled = !running;
        PauseButton.IsEnabled = running && CommitMode == BatchCommitMode.PerFile; CancelButton.IsEnabled = running;
        if (!running) { _resumeSignal?.TrySetResult(true); _resumeSignal = null; PauseButton.Content = "Pause"; _paused = false; }
    }
    private void UpdateSummary()
    {
        if (TotalsText == null) return;
        var bytes = _entries.Where(x => x.StatusText == "Ready").Sum(x => x.Size);
        TotalsText.Text = $"{_entries.Count} files · {FormatBytes(_entries.Sum(x => x.Size))} total · {FormatBytes(bytes)} ready";
        RetryButton.IsEnabled = _runCts == null && _entries.Any(x => x.StatusText is "Failed" or "Cancelled" or "Uncertain");
        RefreshSourceButton.IsEnabled = _runCts == null && _entries.Any(x => x.StatusText == "Changed");
        ApplyQueueFilter();
        SaveQueue();
    }
    private void RestoreQueue(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!_persistQueue) return;
            var saved = _queueStore.Load(_repository, _branch);
            if (saved == null) return;
            if (OctoShipDialog.Show(this, $"Restore {saved.Entries.Length} saved queue entries for {_repository} ({_branch})?\n\nLocal files and remote destinations will be checked again. If an upload was interrupted, check GitHub before retrying it: publication may already have completed. Choosing No replaces the saved queue with the current selection.", "Recover upload queue", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
            _entries.Clear();
            foreach (var row in saved.Entries)
            {
                var entry = new BatchUploadEntry(PersistentUploadQueueStore.RestoreItem(row), row.CommitMessage)
                {
                    StatusText = row.Status == "Uploaded" ? "Uploaded" : row.Status is "Uploading" or "Cancelled" or "Uncertain" ? "Uncertain" : row.Status == "Changed" ? "Changed" : "Ready",
                    Url = row.Url,
                    Error = row.Status is "Uploading" or "Cancelled" or "Uncertain" ? "Previous upload was interrupted. Check GitHub before retrying." : null,
                    ProgressText = row.Status == "Uploaded" ? "100%" : "?"
                };
                _entries.Add(entry);
            }
            CommitModeBox.SelectedIndex = saved.CommitMode == 1 && _uploadBatch != null ? 1 : 0;
            BatchMessageBox.Text = saved.BatchMessage;
        }
        catch (Exception ex) { OctoShipDialog.Show(this, "The saved queue could not be restored: " + ex.Message, "Queue recovery"); }
        finally { _recoveryLoaded = true; UpdateSummary(); }
    }

    private void SaveQueue()
    {
        if (!_persistQueue || !_recoveryLoaded) return;
        try
        {
            if (_entries.Count == 0 || _entries.All(x => x.StatusText == "Uploaded")) { _queueStore.Delete(_repository, _branch); return; }
            _queueStore.Save(new PersistentUploadQueueStore.Snapshot(1, _repository, _branch, CommitModeBox.SelectedIndex, BatchMessageBox.Text,
                _entries.Select(x => new PersistentUploadQueueStore.Entry(x.SourcePath, x.DestinationPath, x.CommitMessage,
                    x.Item.CapturedLength, x.Item.CapturedLastWriteTimeUtc, x.StatusText, x.Url)).ToArray()));
        }
        catch (Exception ex)
        {
            if (_saveWarningShown) return;
            _saveWarningShown = true;
            OctoShipDialog.Show(this, "Queue recovery could not be saved. Keep this window open until finished. " + ex.Message, "Queue recovery unavailable");
        }
    }

    private static string FormatBytes(long bytes) => bytes < 1024 * 1024 ? $"{bytes / 1024d:0.#} KB" : $"{bytes / (1024d * 1024):0.##} MB";
    private static string Estimate(TimeSpan elapsed, long sent, long total)
    { if (elapsed.TotalSeconds < 1 || sent <= 0) return "Estimating…"; var rate = sent / elapsed.TotalSeconds; var remaining = TimeSpan.FromSeconds(Math.Max(0, total - sent) / rate); return $"{FormatBytes((long)rate)}/s · {remaining:mm\\:ss} left"; }
}
