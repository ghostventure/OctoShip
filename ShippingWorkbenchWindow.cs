using System;
using System.IO;
using System.Linq;
using System.Net.NetworkInformation;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Media;

namespace FileToGitHub;

/// <summary>A sequential, explicitly reviewed shipment and read-only delivery checks.</summary>
public sealed class ShippingWorkbenchWindow : Window
{
    private readonly ShippingWorkbenchService _service;
    private readonly Func<string?> _token;
    private readonly CancellationTokenSource _lifetime = new();
    private readonly TextBox _repository = new(), _branch = new(), _folder = new(), _destination = new(), _exclusions = new(), _newBranch = new(), _title = new(), _tag = new(), _releaseName = new();
    private readonly TextBox _output = new() { IsReadOnly = true, AcceptsReturn = true, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, MinHeight = 160, MaxHeight = 360 };
    private readonly DataGrid _files = new() { IsReadOnly = true, AutoGenerateColumns = true, Height = 230 };
    private readonly ComboBox _drafts = new() { DisplayMemberPath = "Tag", MinWidth = 200 };
    private readonly StackPanel _root = new() { Margin = new Thickness(16) };
    private readonly Button _ship = new() { Content = "3. Create branch, upload and open draft PR", IsEnabled = false };
    private ShipReview? _review;
    private bool _busy;
    private string[] _assets = Array.Empty<string>();
    private string? _pagesUrl;
    private readonly ShippingOperationJournal _journal = new();
    private readonly DataGrid _attemptHistory = new() { IsReadOnly = true, AutoGenerateColumns = true, Height = 190 };
    private readonly TextBlock _storageSummary = new() { TextWrapping = TextWrapping.Wrap, Foreground = Brushes.WhiteSmoke };
    private bool _networkReviewRequired;
    private bool _closeoutShown;
    private int _networkChangeVersion;
    public ShippingWorkbenchWindow(HttpClient http, Func<string?> tokenProvider, string repository, string branch, string remoteFolder)
    {
        UniformUi.Prepare(this);
        _service = new(http); _token = tokenProvider;
        Title = "Ship project & delivery checks — OctoShip"; Width = 890; Height = 800; MinWidth = 430; MinHeight = 400;
        WindowStartupLocation = WindowStartupLocation.CenterOwner; Background = new SolidColorBrush(Color.FromRgb(16, 21, 30)); Foreground = Brushes.WhiteSmoke;
        Content = new ScrollViewer { Content = _root, VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        _root.Children.Add(new TextBlock { Text = "Ship project & delivery checks", FontSize = 22, TextWrapping = TextWrapping.Wrap });
        _root.SetResourceReference(MarginProperty, "PagePadding");
        UniformUi.SetDestination(this, () => _repository.Text + "  /  " + _branch.Text);
        Field(_root, "Repository (owner/name)", _repository, repository); Field(_root, "Base branch", _branch, branch);
        var tabs = new TabControl(); _root.Children.Add(tabs);
        var ship = Tab(tabs, "_Ship project");
        Note(ship, "1. Choose a folder and exclusions. 2. Review changed files and branch rules. 3. Ship to a new branch and draft PR. Unchanged content is skipped; no remote files are deleted. Uploads are capped at 100 changed files, 50 MiB each. Content scanning is heuristic; binary and large files can have incomplete scans, shown below.");
        Field(ship, "Local folder", _folder, "");
        Button(ship, "Browse / relink local _folder", () =>
        {
            using var picker = new System.Windows.Forms.FolderBrowserDialog { Description = Directory.Exists(_folder.Text) ? "Choose the project folder to review." : "The saved folder is unavailable. Reconnect its drive or choose the matching project folder, then review again." };
            if (picker.ShowDialog() == System.Windows.Forms.DialogResult.OK)
            {
                if (!Directory.Exists(_folder.Text) && Directory.Exists(picker.SelectedPath) && OctoShipDialog.Show(this, "The previous folder is unavailable. Use this replacement folder and run a fresh review? OctoShip cannot prove it is the same volume or project.", "Relink local project folder", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return Task.CompletedTask;
                _folder.Text = picker.SelectedPath;
            }
            return Task.CompletedTask;
        });
        Field(ship, "Destination folder (blank = repository root)", _destination, remoteFolder);
        Field(ship, "Exclusion globs, one per line (bin, obj and node_modules contents excluded by default)", _exclusions, "*.zip\n*.exe\n*.dll\n*.pdb"); _exclusions.AcceptsReturn = true; _exclusions.Height = 75;
        Field(ship, "New branch", _newBranch, "ship/" + DateTime.Now.ToString("yyyyMMdd-HHmmss"));
        Field(ship, "Commit / draft pull-request title", _title, "Ship project changes");
        Button(ship, "2. _Review files and rules", async () =>
        {
            _review = null; _ship.IsEnabled = false; _files.ItemsSource = null;
            if (_networkReviewRequired || !NetworkInterface.GetIsNetworkAvailable()) throw new InvalidOperationException("Network availability changed since the last review. Reconnect, then review again to refresh GitHub state.");
            var reviewedNetworkVersion = _networkChangeVersion;
            var cloudFiles = FindCloudPlaceholders(_folder.Text);
            if (cloudFiles.Length > 0 && OctoShipDialog.Show(this, "Windows marks some project files as offline or recallable placeholders. Reading them may download their contents from the cloud provider. Continue?\n\n" + string.Join("\n", cloudFiles.Take(12)) + (cloudFiles.Length > 12 ? $"\n…and {cloudFiles.Length - 12} more." : ""), "Cloud files may download", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
            var review = await _service.ReviewAsync(_repository.Text.Trim(), _branch.Text.Trim(), _folder.Text, _destination.Text.Trim('/'), Exclusions(), Token(), _lifetime.Token);
            var diskReport = DiskSpacePreflight(review);
            var rules = "Base branch " + review.Branch + ":\n" + await _service.RulesAsync(review.Repository, review.Branch, Token(), _lifetime.Token);
            rules += "\n\nNew branch " + _newBranch.Text.Trim() + ":\n" + await _service.RulesAsync(review.Repository, _newBranch.Text.Trim(), Token(), _lifetime.Token);
            if (reviewedNetworkVersion != _networkChangeVersion || !NetworkInterface.GetIsNetworkAvailable()) throw new InvalidOperationException("Network state changed during review. Review again when the connection is stable.");
            _networkReviewRequired = false;
            _review = review; _files.ItemsSource = review.Files.Select(x => new { x.Destination, x.Size, x.Status }).ToArray();
            _output.Text = "Reviewed commit " + review.Commit + "\n" + diskReport + "\n\n" + rules; _ship.IsEnabled = !_networkReviewRequired;
        });
        ship.Children.Add(_files); Style(_ship, "Create branch upload and draft pull request"); ship.Children.Add(_ship);
        _ship.Click += async (_, _) =>
        {
            if (_busy || _review == null) return;
            var review = _review;
            if (_networkReviewRequired || !NetworkInterface.GetIsNetworkAvailable()) { _review = null; _ship.IsEnabled = false; throw new InvalidOperationException("Network changed since review. Review again before shipping."); }
            var changed = review.Files.Where(x => !x.Status.StartsWith("Same content", StringComparison.Ordinal)).ToArray();
            var fingerprint = _journal.Fingerprint(review.Repository, review.Branch, review.Commit, changed);
            var prior = _journal.Read().Where(x => x.Fingerprint == fingerprint && (x.Outcome is "Succeeded" or "Started / outcome unknown" or "Failed / inspect remote")).OrderByDescending(x => x.StartedUtc).FirstOrDefault();
            if (prior != null && OctoShipDialog.Show(this, $"A matching shipment was already {prior.Outcome.ToLowerInvariant()} on {prior.StartedUtc.ToLocalTime():g}. GitHub may already contain these exact reviewed files. Inspect the repository/branch before retrying. Continue anyway?", "Possible duplicate shipment", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
            if (OctoShipDialog.Show(this, $"Create {_newBranch.Text} in {review.Repository}, upload {review.Files.Count(x => !x.Status.StartsWith("Same content", StringComparison.Ordinal))} changed files, and create a draft pull request into {review.Branch}?\n\nReview the file list and scan statuses before proceeding.", "Ship reviewed project", MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No) != MessageBoxResult.Yes) return;
            var started = DateTime.UtcNow; var bytes = changed.Sum(x => x.Size);
            _journal.Append(new(started, review.Repository, review.Branch, changed.Length, bytes, fingerprint, "Started / outcome unknown", "Shipment started; remote outcome is not confirmed until the operation returns."));
            await Run(async () =>
            {
                try
                {
                    var result = await _service.ShipAsync(review, _newBranch.Text.Trim(), _title.Text, Token(), _lifetime.Token);
                    _journal.Append(new(started, review.Repository, review.Branch, changed.Length, bytes, fingerprint, "Succeeded", SecurityBoundaries.Redact(result)));
                    _output.Text = result; _review = null; _ship.IsEnabled = false;
                }
                catch (Exception ex)
                {
                    _journal.Append(new(started, review.Repository, review.Branch, changed.Length, bytes, fingerprint, "Failed / inspect remote", SecurityBoundaries.Redact(ex.Message)));
                    throw;
                }
                finally { RefreshOperationCenter(); }
            });
        };
        Button(ship, "Inspect local _Git branch and changes", async () => _output.Text = await ShippingWorkbenchService.LocalGitAsync(_folder.Text, _lifetime.Token));
        foreach (var input in new[] { _repository, _branch, _folder, _destination, _exclusions, _newBranch }) input.TextChanged += (_, _) => { _review = null; _ship.IsEnabled = false; };

        var checks = Tab(tabs, "_Repository checks");
        Button(checks, "Check account and permissions", async () => _output.Text = await _service.DiagnosticsAsync(_repository.Text.Trim(), Token(), _lifetime.Token));
        Button(checks, "Explain branch rules", async () => _output.Text = await _service.RulesAsync(_repository.Text.Trim(), _branch.Text.Trim(), Token(), _lifetime.Token));
        Button(checks, "Check Pages site, build and domain health", async () =>
        {
            _pagesUrl = null; _output.Text = await _service.PagesAsync(_repository.Text.Trim(), Token(), _lifetime.Token);
            var match = System.Text.RegularExpressions.Regex.Match(_output.Text, "\"html_url\"\\s*:\\s*\"(https://[^\"]+)\"");
            if (match.Success) _pagesUrl = match.Groups[1].Value;
        });
        Button(checks, "Open Pages site", () => { if (_pagesUrl == null) throw new InvalidOperationException("Check Pages first; an available site URL is required."); TrustedProcess.Start(new System.Diagnostics.ProcessStartInfo(_pagesUrl) { UseShellExecute = true }); return Task.CompletedTask; });
        Note(checks, "Pages build data can be unavailable for an Actions-based deployment. An unavailable endpoint is reported without assuming the website failed. GitHub CLI attestation verification uses its own signed-in account.");
        Button(checks, "Verify artifact attestation", async () =>
        {
            var picker = new Microsoft.Win32.OpenFileDialog { Title = "Select artifact to verify" };
            if (picker.ShowDialog(this) == true) _output.Text = await ShippingWorkbenchService.AttestationAsync(_repository.Text.Trim(), picker.FileName, _lifetime.Token);
        });

        var release = Tab(tabs, "_Release recovery");
        Note(release, "Resume missing assets on an existing draft. Same-name assets are downloaded and compared with your local file; mismatches remain untouched. Publishing remains a separate action in Release publisher.");
        Button(release, "Load draft releases", async () => { _drafts.ItemsSource = await _service.DraftsAsync(_repository.Text.Trim(), Token(), _lifetime.Token); _output.Text = "Select the draft to resume, then select local assets."; });
        Style(_drafts, "Existing draft release"); release.Children.Add(_drafts);
        Button(release, "Select local release assets", () =>
        {
            var picker = new Microsoft.Win32.OpenFileDialog { Multiselect = true };
            if (picker.ShowDialog(this) == true) { _assets = picker.FileNames; _output.Text = "Selected assets:\n" + string.Join("\n", _assets.Select(Path.GetFileName)); }
            return Task.CompletedTask;
        });
        Button(release, "Upload missing assets to selected draft", async () =>
        {
            if (_drafts.SelectedItem is not ReleaseRecovery draft || _assets.Length == 0) throw new InvalidOperationException("Select an existing draft and local assets first.");
            if (OctoShipDialog.Show(this, $"Upload missing assets to draft {draft.Tag} (ID {draft.Id}) in {_repository.Text}?", "Resume draft", MessageBoxButton.YesNo, MessageBoxImage.Question, MessageBoxResult.No) != MessageBoxResult.Yes) return;
            _output.Text = await _service.RecoverAsync(_repository.Text.Trim(), draft.Id, _assets, Token(), _lifetime.Token);
        });
        Field(release, "Release tag to test", _tag, "");
        Button(release, "Test release downloads and SHA-256", async () => _output.Text = await _service.TestReleaseAsync(_repository.Text.Trim(), _tag.Text.Trim(), _assets, Token(), _lifetime.Token));
        Note(release, "Downloads are streamed without saving. Matching local asset names supply trusted comparison hashes; otherwise a GitHub SHA-256 digest is used when available. A download without either reference is explicitly unverified. Limit: 2 GiB per asset.");

        var recipe = Tab(tabs, "_Project recipe");
        Note(recipe, "Portable JSON stores this repository, base branch, destination folder, exclusions and release naming convention. It never stores the selected local folder or account token. Import updates the Ship project fields; review again before shipping.");
        Field(recipe, "Release naming convention", _releaseName, "v{version}");
        Button(recipe, "Export project recipe", () =>
        {
            var value = new ProjectRecipe(1, _repository.Text.Trim(), _branch.Text.Trim(), _destination.Text.Trim('/'), Exclusions(), _releaseName.Text);
            ShippingWorkbenchService.ValidateRecipe(value);
            var picker = new Microsoft.Win32.SaveFileDialog { Filter = "OctoShip project recipe (*.json)|*.json", FileName = "octoship.project.json" };
            if (picker.ShowDialog(this) == true) { File.WriteAllText(picker.FileName, JsonSerializer.Serialize(value, new JsonSerializerOptions { WriteIndented = true })); _output.Text = "Exported portable project recipe."; }
            return Task.CompletedTask;
        });
        Button(recipe, "Import project recipe", () =>
        {
            var picker = new Microsoft.Win32.OpenFileDialog { Filter = "OctoShip project recipe (*.json)|*.json" };
            if (picker.ShowDialog(this) != true) return Task.CompletedTask;
            if (new FileInfo(picker.FileName).Length > 65536) throw new InvalidOperationException("Recipe exceeds 64 KiB.");
            var value = JsonSerializer.Deserialize<ProjectRecipe>(SecurityBoundaries.ReadBoundedJson(picker.FileName, 65536)) ?? throw new InvalidOperationException("Invalid recipe."); ShippingWorkbenchService.ValidateRecipe(value);
            _repository.Text = value.Repository; _branch.Text = value.BaseBranch; _destination.Text = value.DestinationFolder; _exclusions.Text = string.Join("\n", value.Exclusions); _releaseName.Text = value.ReleaseName;
            _output.Text = "Recipe imported. Choose your local folder and review before shipping."; return Task.CompletedTask;
        });
        var operations = Tab(tabs, "_Operations & storage");
        Note(operations, "Workflow map: choose source → inspect local files and GitHub base → review rules and content → create branch → upload → verify → open draft PR. GitHub is authoritative for remote commits; a lost response can leave the remote outcome uncertain.");
        Button(operations, "Refresh attempt history and storage", () => { RefreshOperationCenter(); return Task.CompletedTask; });
        _attemptHistory.ItemsSource = _journal.Read().OrderByDescending(x => x.StartedUtc).Select(x => new { When = x.StartedUtc.ToLocalTime().ToString("g"), x.Repository, x.Branch, x.FileCount, Outcome = x.Outcome, x.Summary }).ToArray();
        operations.Children.Add(_attemptHistory);
        operations.Children.Add(_storageSummary);
        Button(operations, "Preview stale temporary queue-file cleanup", () => { PreviewCleanup(); return Task.CompletedTask; });
        RefreshOperationCenter();
        Style(_output, "Operation results"); _root.Children.Add(_output);
        var cancel = new Button { Content = "Cancel active operation", Margin = new Thickness(0, 6, 0, 0) };
        Style(cancel, "Cancel active operation"); cancel.Click += (_, _) => { _lifetime.Cancel(); _output.Text += "\nCancellation requested. Close and reopen this window to start another operation."; }; _root.Children.Add(cancel);
        Closing += (_, e) => { if (_busy) { e.Cancel = true; _output.Text += "\nWait for completion or cancel before closing."; } };
        NetworkChange.NetworkAddressChanged += NetworkAddressChanged;
        Closed += (_, _) => { NetworkChange.NetworkAddressChanged -= NetworkAddressChanged; _lifetime.Cancel(); _lifetime.Dispose(); };
        Closing += (_, _) => ShowCloseout();
    }
    private string Token() => _token() ?? throw new InvalidOperationException("Sign in to GitHub first.");
    private string[] Exclusions() => _exclusions.Text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries).Select(x => x.Trim()).Where(x => x.Length > 0).ToArray();
    private void NetworkAddressChanged(object? sender, EventArgs e)
    {
        Interlocked.Increment(ref _networkChangeVersion);
        var available = NetworkInterface.GetIsNetworkAvailable();
        Dispatcher.BeginInvoke(new Action(() =>
        {
            _networkReviewRequired = true;
            _review = null; _ship.IsEnabled = false;
            _output.Text = available
                ? "Network address changed. GitHub branch/permission state may have changed; review again before shipping."
                : "Network is unavailable. Current remote state is unknown until you reconnect and check again.";
        }));
    }

    private static string[] FindCloudPlaceholders(string root)
    {
        if (!Directory.Exists(root)) return Array.Empty<string>();
        var found = new System.Collections.Generic.List<string>(); var pending = new System.Collections.Generic.Stack<string>(); pending.Push(Path.GetFullPath(root)); int examined = 0;
        while (pending.Count > 0 && examined < 10000)
        {
            string[] entries; try { entries = Directory.GetFileSystemEntries(pending.Pop()); } catch { continue; }
            foreach (var path in entries)
            {
                if (++examined > 10000) break;
                try
                {
                    var attributes = File.GetAttributes(path);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) continue;
                    if ((attributes & FileAttributes.Directory) != 0) pending.Push(path);
                    else if ((attributes & (FileAttributes.Offline | (FileAttributes)0x00400000)) != 0) found.Add(Path.GetRelativePath(root, path));
                }
                catch { /* Inaccessible means the OS has not supplied reliable placeholder state. */ }
            }
        }
        return found.ToArray();
    }

    private static string DiskSpacePreflight(ShipReview review)
    {
        try
        {
            var root = Path.GetPathRoot(Path.GetFullPath(review.Files.FirstOrDefault()?.Source ?? review.Files.FirstOrDefault()?.Destination ?? Environment.CurrentDirectory));
            // Destination is a repository path; use a reviewed local source when one exists.
            var source = review.Files.FirstOrDefault()?.Source;
            if (source != null) root = Path.GetPathRoot(Path.GetFullPath(source));
            if (string.IsNullOrWhiteSpace(root)) return "Disk-space preflight: local volume is unknown; continuing without an estimate.";
            var drive = new DriveInfo(root); if (!drive.IsReady) return "Disk-space preflight: local volume is not ready; available space is unknown.";
            var bytes = review.Files.Where(x => !x.Status.StartsWith("Same content", StringComparison.Ordinal)).Sum(x => x.Size);
            var required = checked(bytes + 64L * 1024 * 1024);
            return $"Disk-space preflight: {FormatBytes(drive.AvailableFreeSpace)} available; up to {FormatBytes(required)} considered for staging and safety headroom. " +
                   (drive.AvailableFreeSpace < required ? "Low-space warning: free space is below this estimate; free space or choose a smaller shipment." : "Estimate passes. This is an estimate, not a reservation.");
        }
        catch (Exception ex) { return "Disk-space preflight unavailable: " + ex.Message + " No capacity guarantee can be made."; }
    }

    private void RefreshOperationCenter()
    {
        _attemptHistory.ItemsSource = _journal.Read().OrderByDescending(x => x.StartedUtc).Select(x => new { When = x.StartedUtc.ToLocalTime().ToString("g"), x.Repository, x.Branch, x.FileCount, Outcome = x.Outcome, x.Summary }).ToArray();
        var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub");
        long bytes = 0; int count = 0;
        try
        {
            if (Directory.Exists(root))
            {
                var pending = new System.Collections.Generic.Stack<string>(); pending.Push(root);
                while (pending.Count > 0 && count < 100000)
                {
                    string[] entries; try { entries = Directory.GetFileSystemEntries(pending.Pop()); } catch { continue; }
                    foreach (var path in entries)
                    {
                        try
                        {
                            var attributes = File.GetAttributes(path); if ((attributes & FileAttributes.ReparsePoint) != 0) continue;
                            if ((attributes & FileAttributes.Directory) != 0) pending.Push(path);
                            else { bytes += new FileInfo(path).Length; count++; }
                        }
                        catch { }
                    }
                }
            }
            _storageSummary.Text = $"Local OctoShip data: {FormatBytes(bytes)} in {count} files under {root}. Credentials are excluded from this operation history. Cleanup preview targets only stale temporary queue files older than 7 days; saved queues and app preferences are preserved.";
        }
        catch (Exception ex) { _storageSummary.Text = "Storage usage could not be fully measured: " + ex.Message; }
    }

    private void PreviewCleanup()
    {
        var queueRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "UploadQueues");
        var stale = Directory.Exists(queueRoot) ? Directory.GetFiles(queueRoot, "*.tmp", SearchOption.TopDirectoryOnly).Where(path => File.GetLastWriteTimeUtc(path) < DateTime.UtcNow.AddDays(-7)).ToArray() : Array.Empty<string>();
        if (stale.Length == 0) { OctoShipDialog.Show(this, "No stale temporary queue files older than 7 days were found. Saved queue JSON files are never selected.", "Cleanup preview", MessageBoxButton.OK, MessageBoxImage.Information); return; }
        var listing = stale.Select(path => $"{Path.GetFileName(path)} · {FormatBytes(new FileInfo(path).Length)}").ToArray();
        var total = stale.Sum(path => new FileInfo(path).Length);
        if (OctoShipDialog.Show(this, $"Cleanup preview: {stale.Length} temporary files, {FormatBytes(total)} total. Only *.tmp files directly inside the local UploadQueues folder, last modified more than 7 days ago, qualify.\n\n{string.Join("\n", listing.Take(20))}{(listing.Length > 20 ? $"\n…and {listing.Length - 20} more." : "")}\n\nDelete these temporary files?", "Review local cleanup", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes) return;
        var deleted = 0; var errors = new System.Collections.Generic.List<string>();
        foreach (var path in stale)
        {
            try
            {
                if (!string.Equals(Path.GetDirectoryName(Path.GetFullPath(path)), Path.GetFullPath(queueRoot), StringComparison.OrdinalIgnoreCase) || (File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0 || File.GetLastWriteTimeUtc(path) >= DateTime.UtcNow.AddDays(-7)) continue;
                File.Delete(path); deleted++;
            }
            catch (Exception ex) { errors.Add(Path.GetFileName(path) + ": " + ex.Message); }
        }
        RefreshOperationCenter();
        OctoShipDialog.Show(this, $"Deleted {deleted} stale temporary file(s). Saved queues were preserved." + (errors.Count > 0 ? "\n\nCould not remove:\n" + string.Join("\n", errors.Take(8)) : ""), "Cleanup complete", MessageBoxButton.OK, errors.Count > 0 ? MessageBoxImage.Warning : MessageBoxImage.Information);
    }

    private void ShowCloseout()
    {
        if (_busy || _closeoutShown) return;
        _closeoutShown = true;
        var rows = _journal.Read().OrderByDescending(x => x.StartedUtc).Take(5).ToArray();
        var summary = rows.Length == 0 ? "No shipping attempts recorded in this local history." : string.Join("\n", rows.Select(x => $"{x.StartedUtc.ToLocalTime():g} · {x.Outcome} · {x.Repository}/{x.Branch} · {x.FileCount} file(s)"));
        OctoShipDialog.Show(this, "Session closeout — recent shipping operations\n\n" + summary + "\n\nAny row marked outcome unknown or inspect remote needs a GitHub check before retrying.", "OctoShip session closeout", MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private static string FormatBytes(long value) => value < 1024 * 1024 ? $"{value / 1024d:0.#} KB" : value < 1024L * 1024 * 1024 ? $"{value / (1024d * 1024):0.##} MB" : $"{value / (1024d * 1024 * 1024):0.##} GB";
    private async Task Run(Func<Task> action)
    {
        if (_busy || _lifetime.IsCancellationRequested) return;
        _busy = true; _output.Text = "Working…";
        // Keep the editable review inputs fixed until the operation completes.
        foreach (var child in _root.Children.OfType<Control>().Where(x => x is TabControl or TextBox)) if (child != _output) child.IsEnabled = false;
        try { await action(); }
        catch (OperationCanceledException) { _output.Text = "Cancelled. A remote mutation may have completed; inspect GitHub before retrying."; }
        catch (Exception ex) { _output.Text = ex.Message; }
        finally { _busy = false; foreach (var child in _root.Children.OfType<Control>()) child.IsEnabled = true; _ship.IsEnabled = _review != null; }
    }
    private void Button(Panel panel, string title, Func<Task> action)
    {
        var button = new Button { Content = title, Margin = new Thickness(0, 5, 0, 5), Padding = new Thickness(8), HorizontalContentAlignment = HorizontalAlignment.Left };
        Style(button, title.Replace("_", "")); button.Click += async (_, _) => await Run(action); panel.Children.Add(button);
    }
    private static StackPanel Tab(TabControl tabs, string title)
    {
        var panel = new StackPanel { Margin = new Thickness(10), Background = new SolidColorBrush(Color.FromRgb(16, 21, 30)) };
        tabs.Items.Add(new TabItem { Header = title, Content = panel }); return panel;
    }
    private static void Field(Panel panel, string title, TextBox box, string value)
    {
        panel.Children.Add(new TextBlock { Text = title, Foreground = Brushes.WhiteSmoke, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 5, 0, 3) }); Style(box, title); box.Text = value; panel.Children.Add(box);
    }
    private new static void Style(Control control, string name)
    {
        control.Background = new SolidColorBrush(Color.FromRgb(29, 43, 60)); control.Foreground = Brushes.WhiteSmoke; control.Padding = new Thickness(6); AutomationProperties.SetName(control, name);
    }
    private static void Note(Panel panel, string text) => panel.Children.Add(new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap, Foreground = Brushes.WhiteSmoke, Margin = new Thickness(0, 6, 0, 8) });
}
