using Microsoft.Win32;
using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;

namespace FileToGitHub;

public sealed class BatchUploadFile
{
    public BatchUploadFile(string sourcePath, string destinationPath, string commitMessage, long size)
    { SourcePath = sourcePath; DestinationPath = destinationPath; CommitMessage = commitMessage; Size = size; }
    public string SourcePath { get; }
    public string DestinationPath { get; }
    public string CommitMessage { get; }
    public long Size { get; }
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
    internal UploadQueueItem Item { get; }
    public string SourcePath => Item.SourcePath;
    public string DestinationPath { get => _destinationPath; set { if (_destinationPath != value) { _destinationPath = value; Item.DestinationPath = UploadQueueItem.NormalizeDestination(value); Changed(nameof(DestinationPath)); } } }
    public string CommitMessage { get => _commitMessage; set { _commitMessage = value ?? ""; Changed(nameof(CommitMessage)); } }
    public long Size { get; }
    public string SizeText => Size < 1024 * 1024 ? $"{Size / 1024d:0.#} KB" : $"{Size / (1024d * 1024):0.##} MB";
    public string ProgressText { get; internal set; } = "—";
    public string StatusText { get; internal set; }
    public string? Error { get; internal set; }
    public string? Url { get; internal set; }
    public bool HasUrl => Uri.TryCreate(Url, UriKind.Absolute, out var uri) && uri.Scheme == Uri.UriSchemeHttps && uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase);
    public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged;
    internal void Changed(string property) => PropertyChanged?.Invoke(this, new System.ComponentModel.PropertyChangedEventArgs(property));
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
    private CancellationTokenSource? _runCts;
    private bool _paused;
    private TaskCompletionSource<bool>? _resumeSignal;

    public BatchUploadWindow(System.Collections.Generic.IEnumerable<UploadQueueItem> items, string repository, string branch,
        string defaultCommitMessage, SingleFileUpload uploadOne, SingleCommitUpload? uploadBatch = null, string transferNotice = "")
    {
        InitializeComponent();
        _repository = repository ?? ""; _branch = branch ?? ""; _defaultCommitMessage = defaultCommitMessage ?? "Upload files";
        _uploadOne = uploadOne ?? throw new ArgumentNullException(nameof(uploadOne)); _uploadBatch = uploadBatch;
        _entries = new ObservableCollection<BatchUploadEntry>((items ?? throw new ArgumentNullException(nameof(items))).Select(item => new BatchUploadEntry(item, _defaultCommitMessage)));
        QueueGrid.ItemsSource = _entries;
        DestinationText.Text = $"{_repository} · {(_branch.Length == 0 ? "default branch" : _branch)}";
        NetworkNotice.Text = transferNotice;
        NetworkNotice.Visibility = string.IsNullOrWhiteSpace(transferNotice) ? Visibility.Collapsed : Visibility.Visible;
        CommitModeBox.SelectedIndex = 0;
        UpdateSummary();
    }

    /// <summary>Final summary after the window closes; null means the user closed before starting.</summary>
    public System.Collections.Generic.IReadOnlyList<BatchUploadResult>? FinalResults { get; private set; }

    private BatchCommitMode CommitMode => CommitModeBox.SelectedIndex == 1 ? BatchCommitMode.SingleBatch : BatchCommitMode.PerFile;
    private void CommitModeBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (QueueGrid == null) return;
        var one = CommitMode == BatchCommitMode.SingleBatch;
        QueueGrid.Columns[3].IsReadOnly = one;
        if (one && _uploadBatch == null) { QueueGrid.Columns[3].Header = "Message (batch callback required)"; StartButton.IsEnabled = false; }
        else { QueueGrid.Columns[3].Header = one ? "Per-file messages ignored" : "Commit message"; StartButton.IsEnabled = true; }
    }
    private void CollisionBox_SelectionChanged(object sender, SelectionChangedEventArgs e) { }
    private void QueueGrid_CellEditEnding(object sender, DataGridCellEditEndingEventArgs e) => Dispatcher.BeginInvoke(new Action(UpdateSummary));
    private void AddFiles_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Multiselect = true, Title = "Add files to upload" };
        if (dialog.ShowDialog(this) != true) return;
        foreach (var item in UploadQueuePlanner.FromFiles(dialog.FileNames))
        {
            var entry = new BatchUploadEntry(item, _defaultCommitMessage);
            if (_entries.Any(x => x.SourcePath.Equals(entry.SourcePath, StringComparison.OrdinalIgnoreCase))) continue;
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
        _entries.Move(index, next); QueueGrid.SelectedItem = selected[0];
    }
    private void ApplyRules_Click(object sender, RoutedEventArgs e) { ApplyRules(); UpdateSummary(); }
    private void ApplyRules()
    {
        var maxMB = 50d;
        if (!double.TryParse(MaxSizeBox.Text, out maxMB) || maxMB <= 0) { MessageBox.Show(this, "Enter a positive maximum size in MB.", "Invalid size", MessageBoxButton.OK, MessageBoxImage.Warning); return; }
        var patterns = IgnoreBox.Text.Split(new[] { ',', ';', '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).Select(x => x.Trim()).Where(x => x.Length > 0).ToArray();
        foreach (var entry in _entries)
        {
            if (entry.StatusText is "Uploaded" or "Uploading") continue;
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
        QueueGrid.CommitEdit(DataGridEditingUnit.Cell, true); QueueGrid.CommitEdit(DataGridEditingUnit.Row, true); ApplyRules();
        var ready = _entries.Where(x => x.StatusText is "Ready" or "Failed").ToArray();
        if (ready.Length == 0) { MessageBox.Show(this, "There are no ready files to upload.", "Upload", MessageBoxButton.OK, MessageBoxImage.Information); return; }
        var totalBytes = ready.Sum(x => x.Size);
        if (MessageBox.Show(this, $"Upload {ready.Length} files ({FormatBytes(totalBytes)}) to {_repository}?\n\nReview the paths and commit settings before continuing.", "Confirm upload", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
        _runCts = new CancellationTokenSource(); SetRunning(true);
        try
        {
            if (CommitMode == BatchCommitMode.SingleBatch) await RunSingleBatchAsync(ready, _runCts.Token);
            else await RunPerFileAsync(ready, _runCts.Token);
        }
        finally { SetRunning(false); _runCts.Dispose(); _runCts = null; }
        FinalResults = _entries.Select(x => new BatchUploadResult(x.SourcePath, x.StatusText == "Uploaded", x.Url, x.Error)).ToArray();
        var ok = FinalResults.Count(x => x.Succeeded); var skipped = _entries.Count(x => x.StatusText == "Skipped"); var failed = FinalResults.Count(x => !x.Succeeded) - skipped;
        MessageBox.Show(this, $"Batch finished.\n\nUploaded: {ok}\nSkipped: {skipped}\nFailed or cancelled: {Math.Max(0, failed)}", "Upload summary", MessageBoxButton.OK, ok == ready.Length ? MessageBoxImage.Information : MessageBoxImage.Warning);
    }
    private async Task RunPerFileAsync(BatchUploadEntry[] entries, CancellationToken token)
    {
        var sw = Stopwatch.StartNew(); long sent = 0; var processed = 0;
        foreach (var entry in entries)
        {
            if (_paused && _resumeSignal != null) await _resumeSignal.Task.WaitAsync(token);
            if (token.IsCancellationRequested) { entry.StatusText = "Cancelled"; entry.Error = "Cancelled before upload."; entry.Refresh(); continue; }
            entry.StatusText = "Uploading"; entry.ProgressText = "0%"; entry.Refresh();
            var file = new BatchUploadFile(entry.SourcePath, entry.DestinationPath, entry.CommitMessage, entry.Size);
            var progress = new Progress<double>(value => { entry.ProgressText = $"{Math.Clamp(value, 0, 100):0}%"; OverallProgress.Value = Math.Clamp((processed + value / 100d) / entries.Length * 100, 0, 100); ProgressText.Text = Estimate(sw.Elapsed, sent + (long)(entry.Size * Math.Clamp(value, 0, 100) / 100d), entries.Sum(x => x.Size)); entry.Refresh(); });
            try
            {
                var result = await _uploadOne(file, progress, token); entry.Url = result.Url;
                entry.StatusText = result.Succeeded ? "Uploaded" : "Failed"; entry.Error = result.Error; entry.ProgressText = result.Succeeded ? "100%" : entry.ProgressText;
                if (result.Succeeded) sent += entry.Size;
            }
            catch (OperationCanceledException) { entry.StatusText = "Cancelled"; entry.Error = "Upload cancelled."; }
            catch (Exception ex) { entry.StatusText = "Failed"; entry.Error = ex.Message; }
            processed++; entry.Refresh(); UpdateSummary();
        }
    }
    private async Task RunSingleBatchAsync(BatchUploadEntry[] entries, CancellationToken token)
    {
        if (_uploadBatch == null) throw new InvalidOperationException("The host did not provide a single-commit upload callback.");
        var files = entries.Select(x => new BatchUploadFile(x.SourcePath, x.DestinationPath, x.CommitMessage, x.Size)).ToArray();
        foreach (var entry in entries) { entry.StatusText = "Uploading"; entry.ProgressText = "0%"; entry.Refresh(); }
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
            var results = await _uploadBatch(files, entries[0].CommitMessage, progress, token);
            foreach (var entry in entries)
            {
                var result = results.FirstOrDefault(x => x.SourcePath.Equals(entry.SourcePath, StringComparison.OrdinalIgnoreCase));
                entry.StatusText = result?.Succeeded == true ? "Uploaded" : "Failed"; entry.Url = result?.Url; entry.Error = result?.Error ?? (result == null ? "No result returned by batch callback." : null);
                entry.ProgressText = result?.Succeeded == true ? "100%" : entry.ProgressText; entry.Refresh();
            }
        }
        catch (Exception ex) { foreach (var entry in entries) { entry.StatusText = token.IsCancellationRequested ? "Cancelled" : "Failed"; entry.Error = ex.Message; entry.Refresh(); } }
        OverallProgress.Value = 100; UpdateSummary();
    }
    private void Retry_Click(object sender, RoutedEventArgs e)
    {
        var selected = QueueGrid.SelectedItems.Cast<object>().OfType<BatchUploadEntry>().Where(x => x.StatusText == "Failed").ToArray();
        var retry = selected.Length > 0 ? selected : _entries.Where(x => x.StatusText == "Failed").ToArray();
        foreach (var entry in retry) { entry.StatusText = "Ready"; entry.Error = null; entry.ProgressText = "—"; entry.Refresh(); }
        StartButton.IsEnabled = true; RetryButton.IsEnabled = false; UpdateSummary();
    }
    private void Pause_Click(object sender, RoutedEventArgs e)
    {
        _paused = !_paused;
        if (_paused) { _resumeSignal = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously); PauseButton.Content = "Resume"; }
        else { _resumeSignal?.TrySetResult(true); _resumeSignal = null; PauseButton.Content = "Pause"; }
    }
    private void Cancel_Click(object sender, RoutedEventArgs e) => _runCts?.Cancel();
    private void Close_Click(object sender, RoutedEventArgs e) { if (_runCts != null) { MessageBox.Show(this, "Cancel the active upload before closing."); return; } Close(); }
    private void OpenLink_Click(object sender, RoutedEventArgs e) { if ((sender as Button)?.Tag is string url && Uri.TryCreate(url, UriKind.Absolute, out var uri) && uri.Scheme == "https" && uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase)) Process.Start(new ProcessStartInfo(uri.ToString()) { UseShellExecute = true }); }
    private void SetRunning(bool running)
    {
        StartButton.IsEnabled = !running && (CommitMode != BatchCommitMode.SingleBatch || _uploadBatch != null);
        foreach (var control in new[] { RetryButton, AddFilesButtonControl, RemoveButtonControl, MoveUpButtonControl, MoveDownButtonControl }) control.IsEnabled = !running;
        PauseButton.IsEnabled = running && CommitMode == BatchCommitMode.PerFile; CancelButton.IsEnabled = running;
        if (!running) { _resumeSignal?.TrySetResult(true); _resumeSignal = null; PauseButton.Content = "Pause"; _paused = false; }
    }
    private void UpdateSummary()
    {
        if (TotalsText == null) return;
        var bytes = _entries.Where(x => x.StatusText == "Ready").Sum(x => x.Size);
        TotalsText.Text = $"{_entries.Count} files · {FormatBytes(_entries.Sum(x => x.Size))} total · {FormatBytes(bytes)} ready";
        RetryButton.IsEnabled = _runCts == null && _entries.Any(x => x.StatusText == "Failed");
    }
    private static string FormatBytes(long bytes) => bytes < 1024 * 1024 ? $"{bytes / 1024d:0.#} KB" : $"{bytes / (1024d * 1024):0.##} MB";
    private static string Estimate(TimeSpan elapsed, long sent, long total)
    { if (elapsed.TotalSeconds < 1 || sent <= 0) return "Estimating…"; var rate = sent / elapsed.TotalSeconds; var remaining = TimeSpan.FromSeconds(Math.Max(0, total - sent) / rate); return $"{FormatBytes((long)rate)}/s · {remaining:mm\\:ss} left"; }
}
