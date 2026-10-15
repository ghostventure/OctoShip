using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace FileToGitHub;

/// <summary>Offline preparation plus explicitly reviewed atomic publishing. All remote reads are refreshed before publication.</summary>
public sealed class ShippingPreparationWindow : Window
{
    public sealed class Mapping
    {
        public string Source { get; set; } = "";
        public string Destination { get; set; } = "";
    }
    private readonly HttpClient _http;
    private readonly Func<string?> _token;
    private readonly Func<string?> _account;
    private readonly TextBox _root = new(), _repository = new(), _branch = new(), _folder = new(), _expectedAccount = new(), _version = new(), _asset = new(), _channel = new(), _message = new();
    private readonly TextBox _report = new() { AcceptsReturn = true, IsReadOnly = true, Height = 220, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
    private readonly TextBlock _status = new() { TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 10, 0, 0) };
    private readonly ObservableCollection<Mapping> _mappings = new();
    private readonly DataGrid _grid = new() { AutoGenerateColumns = false, Height = 200, CanUserAddRows = false };
    private readonly CancellationTokenSource _lifetime = new();
    private readonly string _staging = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "PreparedFiles", Guid.NewGuid().ToString("N"));
    private readonly Dictionary<string, ShippingProjectProfile> _profiles;
    private static readonly string ProfilePath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "OctoShipForGitHub", "project-bindings.json");
    private bool _busy;
    private string? _visibility;
    private string? _visibilityRepository;
    private string? _selectiveHead;
    private string? _selectiveRepository;
    private string? _selectiveBranch;
    private string? _selectiveDestination;
    private Mapping? _selectiveMapping;
    private bool _selectiveStaged;

    public ShippingPreparationWindow(HttpClient http, Func<string?> token, Func<string?> account, string repository, string branch, string folder)
    {
        UniformUi.Prepare(this);
        _http = http; _token = token; _account = account;
        _profiles = PublicationBindings.Load();
        Title = "OctoShip — Prepare and inspect"; Width = 1000; Height = 850; MinWidth = 700; MinHeight = 600;
        Background = new SolidColorBrush(Color.FromRgb(16, 21, 30)); Foreground = Brushes.WhiteSmoke; WindowStartupLocation = WindowStartupLocation.CenterOwner;
        var panel = new StackPanel { Margin = new Thickness(18) }; Content = new ScrollViewer { Content = panel, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        Field(panel, "Project folder (local checks and saved account binding)", _root, "");
        Button(panel, "Choose project", () => { using var dialog = new System.Windows.Forms.FolderBrowserDialog(); if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK) { _root.Text = dialog.SelectedPath; LoadProfile(); } });
        Field(panel, "Repository owner/name", _repository, repository); Field(panel, "Branch", _branch, branch.Length == 0 ? "main" : branch);
        panel.SetResourceReference(MarginProperty, "PagePadding");
        UniformUi.SetDestination(this, () => _repository.Text + "  /  " + _branch.Text);
        var tabs = new TabControl(); panel.Children.Add(tabs);
        var map = Tab(tabs, "Prepare files");
        Note(map, "Drop files or a folder onto the destination box. Review exact paths below. Preparation works offline. Publishing reads fresh repository permissions, account and branch state, then asks you to approve one atomic commit.");
        Field(map, "Destination folder (blank = repository root); drop here", _folder, folder);
        _folder.AllowDrop = true;
        _folder.PreviewDragOver += (_, e) => { e.Effects = e.Data.GetDataPresent(DataFormats.FileDrop) ? DragDropEffects.Copy : DragDropEffects.None; e.Handled = true; };
        _folder.Drop += (_, e) => { e.Handled = true; if (!_busy && e.Data.GetData(DataFormats.FileDrop) is string[] paths) RunLocal(() => AddPaths(paths)); };
        Button(map, "Add files", () => { var d = new Microsoft.Win32.OpenFileDialog { Multiselect = true }; if (d.ShowDialog(this) == true) AddPaths(d.FileNames); });
        Button(map, "Add project folder", () => AddPaths(new[] { _root.Text }));
        Button(map, "Add empty-folder placeholder", () =>
        {
            using var d = new System.Windows.Forms.FolderBrowserDialog(); if (d.ShowDialog() != System.Windows.Forms.DialogResult.OK) return;
            if (Directory.EnumerateFileSystemEntries(d.SelectedPath).Any()) throw new InvalidOperationException("Choose an empty folder. Git stores files, so a .gitkeep placeholder represents this folder.");
            var relative = Path.GetRelativePath(Path.GetFullPath(_root.Text), d.SelectedPath).Replace('\\', '/');
            if (relative == ".." || relative.StartsWith("../")) throw new InvalidOperationException("The empty folder must be inside the project.");
            var path = Stage(Array.Empty<byte>(), ".gitkeep");
            _mappings.Add(new() { Source = path, Destination = Join(_folder.Text, relative == "." ? ".gitkeep" : relative + "/.gitkeep") });
            _status.Text = "Placeholder staged; your local empty folder is unchanged.";
        });
        _grid.Columns.Add(new DataGridTextColumn { Header = "Local source", Binding = new System.Windows.Data.Binding("Source"), IsReadOnly = true, Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        _grid.Columns.Add(new DataGridTextColumn { Header = "Exact repository destination", Binding = new System.Windows.Data.Binding("Destination"), Width = new DataGridLength(1, DataGridLengthUnitType.Star) });
        _grid.ItemsSource = _mappings; map.Children.Add(_grid);
        Button(map, "Remove selected", () => { if (_grid.SelectedItem is Mapping item) _mappings.Remove(item); });
        Button(map, "Save offline plan", SavePlan); Button(map, "Load offline plan", LoadPlan);
        Field(map, "Commit message", _message, "Publish reviewed files");
        AsyncButton(map, "Validate and publish reviewed batch", PublishAsync);

        var selective = Tab(tabs, "Select changes");
        Note(selective, "Select a mapping above, then load its UTF-8 contents and the remote baseline. Choose individual edit blocks. The staged result preserves unselected remote text and leaves the source file untouched. Limited to 2,000 lines and 1 MiB per file.");
        var hunks = new StackPanel(); string baseline = ""; IReadOnlyList<SelectiveTextChange>? changes = null; Mapping? selected = null;
        AsyncButton(selective, "Load selected file changes", async () =>
        {
            var candidate = _grid.SelectedItem as Mapping ?? throw new InvalidOperationException("Select a file on Prepare files first.");
            if (_selectiveStaged && _selectiveMapping != null && _mappings.Contains(_selectiveMapping) && candidate != _selectiveMapping) throw new InvalidOperationException("Publish or remove the already staged selective file before selecting another file.");
            selected = candidate;
            if (new FileInfo(selected.Source).Length > 1024 * 1024) throw new IOException("Choose a text file up to 1 MiB.");
            var tokenValue = RequireToken(); var repo = _repository.Text.Trim(); var br = _branch.Text.Trim(); RepositoryWorkflowService.ValidateRepository(repo); RepositoryWorkflowService.ValidateBranch(br);
            var parts = repo.Split('/'); var service = new GitHubAtomicBatchService(_http);
            var head = await service.GetHeadAsync(parts[0], parts[1], br, tokenValue, _lifetime.Token);
            baseline = await ReadRemoteTextAsync(repo, head, selected.Destination);
            var local = new UTF8Encoding(false, true).GetString(File.ReadAllBytes(selected.Source));
            if (local.Contains('\0') || baseline.Contains('\0')) throw new IOException("Binary files cannot be selectively published.");
            changes = SelectiveTextChanges.Compare(baseline, local); hunks.Children.Clear();
            foreach (var change in changes)
            {
                var checkbox = new CheckBox { IsChecked = true, Content = new TextBlock { Text = change.Description, TextWrapping = TextWrapping.Wrap }, Margin = new Thickness(0, 8, 0, 8), Foreground = Brushes.Black };
                checkbox.Checked += (_, _) => change.Include = true; checkbox.Unchecked += (_, _) => change.Include = false; hunks.Children.Add(checkbox);
            }
            _selectiveHead = head; _selectiveRepository = repo; _selectiveBranch = br; _selectiveDestination = selected.Destination;
            _selectiveMapping = selected;
            _status.Text = $"Loaded {changes.Count} edit blocks at commit {head[..12]}.";
        });
        selective.Children.Add(hunks);
        Button(selective, "Stage chosen changes", () =>
        {
            if (changes == null || selected == null || !_mappings.Contains(selected)) throw new InvalidOperationException("Load a mapped file first.");
            if (selected.Destination != _selectiveDestination) throw new InvalidOperationException("Destination changed. Load changes again.");
            selected.Source = Stage(new UTF8Encoding(false, true).GetBytes(SelectiveTextChanges.Apply(baseline, changes)), Path.GetFileName(selected.Destination)); _grid.Items.Refresh();
            _selectiveStaged = true;
            _status.Text = "Chosen changes staged. Local source is untouched. Publish from Prepare files; branch changes require a fresh selection.";
        });

        var accountPanel = Tab(tabs, "Account and visibility");
        Field(accountPanel, "Expected GitHub account for this project", _expectedAccount, "");
        AsyncButton(accountPanel, "Refresh account, commit identity and visibility", RefreshIdentityAsync);
        Button(accountPanel, "Save project account / current visibility binding", () =>
        {
            var key = ProfileKey(); _profiles[key] = new(_expectedAccount.Text.Trim(), _visibilityRepository == _repository.Text.Trim() ? _visibility : null);
            Directory.CreateDirectory(Path.GetDirectoryName(ProfilePath)!); File.WriteAllText(ProfilePath, JsonSerializer.Serialize(_profiles, new JsonSerializerOptions { WriteIndented = true }));
            _status.Text = "Project binding saved locally, without credentials.";
        });
        Note(accountPanel, "GitHub chooses commit identity for API commits. Public profile email is not a commit-email guarantee. Saved account and visibility bindings apply to every publishing workflow for this repository. Conflicting bindings block publication until reviewed.");

        var inspect = Tab(tabs, "Project and release checks");
        Field(inspect, "Expected version / release tag (optional)", _version, "");
        AsyncButton(inspect, "Scan versions, Markdown links and LFS", async () => { var root = _root.Text; var version = _version.Text; var rows = await Task.Run(() => ShippingInspectionService.Inspect(root, version)); _report.Text = string.Join("\n", rows.Select(x => $"{x.File} | {x.Check}: {x.Detail}")); });
        AsyncButton(inspect, "Inspect ZIP contents", async () => { var d = new Microsoft.Win32.OpenFileDialog { Filter = "ZIP archive|*.zip" }; if (d.ShowDialog(this) == true) { var rows = await Task.Run(() => ShippingInspectionService.InspectZip(d.FileName)); _report.Text = string.Join("\n", rows.Select(x => $"{x.File} | {x.Check}: {x.Detail}")); } });
        AsyncButton(inspect, "Inspect installer", async () => { var d = new Microsoft.Win32.OpenFileDialog { Filter = "Windows installer|*.exe;*.msi" }; if (d.ShowDialog(this) == true) _report.Text = await Task.Run(() => ShippingInspectionService.InspectInstaller(d.FileName)); });
        Field(inspect, "Expected updater channel: stable or preview", _channel, "stable"); Field(inspect, "Expected release asset filename", _asset, "");
        AsyncButton(inspect, "Check repository release channel and asset", ValidateChannelAsync);
        Note(inspect, "Release-channel check reads this repository's releases and verifies the selected channel, tag and exact asset name. It does not infer your application's updater implementation or follow download redirects.");

        var support = Tab(tabs, "Support bundle");
        var details = new TextBox { AcceptsReturn = true, Height = 100, TextWrapping = TextWrapping.Wrap }; Field(support, "Describe the failed operation (review redacted output before saving)", details, "");
        Button(support, "Preview redacted support report", () => _report.Text = ShippingInspectionService.Redact($"OctoShip {typeof(ShippingPreparationWindow).Assembly.GetName().Version}\nOS: {Environment.OSVersion}\nUTC: {DateTime.UtcNow:O}\nOperation: {details.Text}\nStatus: {_status.Text}\n\n{_report.Text}"));
        Button(support, "Save current redacted report", () => { var d = new Microsoft.Win32.SaveFileDialog { Filter = "Text support report|*.txt", FileName = "OctoShip-support.txt" }; if (d.ShowDialog(this) == true) { _report.Text = ShippingInspectionService.Redact(_report.Text); File.WriteAllText(d.FileName, _report.Text); _status.Text = "Redacted support report saved. No credentials or automatic log collection included."; } });
        panel.Children.Add(_report); panel.Children.Add(_status);
        Closing += (_, e) => { if (_busy) { e.Cancel = true; _status.Text = "Wait for the active operation to finish before closing."; } };
        Closed += (_, _) => { _lifetime.Cancel(); /* PreparedFiles are retained for explicitly saved offline plans. */ };
    }

    private void AddPaths(IEnumerable<string> paths)
    {
        foreach (var path in paths)
        {
            if (Directory.Exists(path)) foreach (var item in UploadQueuePlanner.FromFolder(path, _folder.Text)) _mappings.Add(new() { Source = item.SourcePath, Destination = item.DestinationPath });
            else foreach (var item in UploadQueuePlanner.FromFiles(new[] { path }, _folder.Text)) _mappings.Add(new() { Source = item.SourcePath, Destination = item.DestinationPath });
        }
        _status.Text = $"Prepared {_mappings.Count} files offline. Edit destination cells to adjust the mapping.";
    }
    private string Stage(byte[] bytes, string name) { Directory.CreateDirectory(_staging); var file = Path.Combine(_staging, Guid.NewGuid().ToString("N") + "-" + name); File.WriteAllBytes(file, bytes); return file; }
    private static string Join(string folder, string file) => UploadQueueItem.NormalizeDestination(folder.Trim('/') + "/" + file);
    private string ProfileKey() => Path.GetFullPath(_root.Text).TrimEnd(Path.DirectorySeparatorChar).ToUpperInvariant() + "|" + _repository.Text.Trim().ToLowerInvariant();
    private void LoadProfile() { if (_profiles.TryGetValue(ProfileKey(), out var p)) _expectedAccount.Text = p.ExpectedAccount; else _expectedAccount.Text = ""; }
    private string RequireToken() => !string.IsNullOrWhiteSpace(_token()) ? _token()! : throw new InvalidOperationException("Connect your GitHub account in the main window first. Offline preparation remains available.");
    private async Task<JsonDocument> GetAsync(string route)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "https://api.github.com/" + route);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", RequireToken()); request.Headers.UserAgent.ParseAdd("OctoShip/1.5"); request.Headers.Accept.ParseAdd("application/vnd.github+json");
        using var response = await _http.SendAsync(request, _lifetime.Token); response.EnsureSuccessStatusCode();
        return JsonDocument.Parse(await response.Content.ReadAsStringAsync(_lifetime.Token));
    }
    private async Task RefreshIdentityAsync()
    {
        var repo = _repository.Text.Trim(); RepositoryWorkflowService.ValidateRepository(repo);
        using var user = await GetAsync("user"); var login = user.RootElement.GetProperty("login").GetString()!;
        using var data = await GetAsync("repos/" + repo); var r = data.RootElement;
        _visibility = r.TryGetProperty("visibility", out var visibility) ? visibility.GetString() : r.GetProperty("private").GetBoolean() ? "private" : "public"; _visibilityRepository = repo;
        var warning = "";
        if (!string.IsNullOrWhiteSpace(_root.Text) && _profiles.TryGetValue(ProfileKey(), out var saved))
        {
            if (saved.Visibility != null && saved.Visibility != _visibility) warning += $"\nWARNING: saved visibility {saved.Visibility} changed to {_visibility}.";
            if (saved.ExpectedAccount.Length > 0 && !saved.ExpectedAccount.Equals(login, StringComparison.OrdinalIgnoreCase)) warning += $"\nWARNING: saved project account {saved.ExpectedAccount} differs from {login}.";
        }
        if (_expectedAccount.Text.Trim().Length > 0 && !_expectedAccount.Text.Trim().Equals(login, StringComparison.OrdinalIgnoreCase)) warning += "\nWARNING: expected account differs from connected account.";
        var profileName = user.RootElement.TryGetProperty("name", out var name) && name.ValueKind == JsonValueKind.String ? name.GetString() : login;
        var profileEmail = user.RootElement.TryGetProperty("email", out var email) && email.ValueKind == JsonValueKind.String ? email.GetString() : "not publicly exposed";
        _report.Text = $"Authenticated account: {login}\nProfile name: {profileName}\nProfile email (not a commit-email guarantee): {profileEmail}\nRepository visibility: {_visibility}\nCommit author/email: GitHub account defaults (exact email not exposed by this check).\nEmail privacy: https://github.com/settings/emails{warning}";
        _status.Text = "Account and repository visibility refreshed.";
    }
    private async Task<string> ReadRemoteTextAsync(string repo, string commit, string path)
    {
        try
        {
            using var data = await GetAsync("repos/" + repo + "/contents/" + string.Join("/", path.Split('/').Select(Uri.EscapeDataString)) + "?ref=" + commit);
            var r = data.RootElement;
            if (r.GetProperty("size").GetInt64() > 1024 * 1024 || r.GetProperty("encoding").GetString() != "base64") throw new IOException("Remote file is too large or not a regular readable file.");
            return new UTF8Encoding(false, true).GetString(Convert.FromBase64String(r.GetProperty("content").GetString()!));
        }
        catch (HttpRequestException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound) { return ""; }
    }
    private async Task PublishAsync()
    {
        _grid.CommitEdit(DataGridEditingUnit.Cell, true); _grid.CommitEdit(DataGridEditingUnit.Row, true);
        if (_mappings.Count is < 1 or > 100) throw new InvalidOperationException("Prepare between 1 and 100 files.");
        var repo = _repository.Text.Trim(); var branch = _branch.Text.Trim(); var token = RequireToken(); var message = _message.Text;
        RepositoryWorkflowService.ValidateRepository(repo); RepositoryWorkflowService.ValidateBranch(branch);
        await RefreshIdentityAsync();
        using var user = await GetAsync("user"); var login = user.RootElement.GetProperty("login").GetString()!;
        var expected = _expectedAccount.Text.Trim();
        if (!string.IsNullOrWhiteSpace(_root.Text) && _profiles.TryGetValue(ProfileKey(), out var profile) && profile.ExpectedAccount.Length > 0) expected = profile.ExpectedAccount;
        if (expected.Length > 0 && !expected.Equals(login, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Connected account differs from the project binding. Switch accounts or explicitly update the saved binding.");
        var parts = repo.Split('/'); var service = new GitHubAtomicBatchService(_http); var head = await service.GetHeadAsync(parts[0], parts[1], branch, token, _lifetime.Token);
        if (_selectiveStaged && _selectiveMapping != null && _mappings.Contains(_selectiveMapping) &&
            (_selectiveHead != head || _selectiveRepository != repo || _selectiveBranch != branch || _selectiveMapping.Destination != _selectiveDestination))
            throw new InvalidOperationException("Selective baseline or destination changed. Load and stage the file changes again.");
        var files = _mappings.Select(x => { var info = new FileInfo(x.Source); return new BatchUploadFile(x.Source, UploadQueueItem.NormalizeDestination(x.Destination), message, info.Length, info.LastWriteTimeUtc); }).ToArray();
        var sensitive = files.Where(x => new FileSafetyRules().Match(x.SourcePath).Count > 0 || new FileSafetyRules().Match(x.DestinationPath).Count > 0).Select(x => x.DestinationPath).ToArray();
        if (sensitive.Length > 0) throw new InvalidOperationException("Sensitive-name files are blocked in this workflow: " + string.Join(", ", sensitive));
        if (OctoShipDialog.Show(this, $"Publish {files.Length} files as {login} to {repo} ({_visibility}), branch {branch}?\n\n{_report.Text}\n\nExisting destinations will be replaced by the reviewed contents.\n\n" + string.Join("\n", files.Select(x => x.DestinationPath)), "Publish reviewed batch", MessageBoxButton.OKCancel, MessageBoxImage.Warning) != MessageBoxResult.OK) return;
        var results = await service.UploadAsync(parts[0], parts[1], branch, token, files, message, head, ct: _lifetime.Token, validateContent: async (path, bytes, ct) =>
        {
            var result = await Task.Run(() => ContentSecretScanner.ScanBytes(bytes, ct), ct);
            if (result.HasFindings) throw new InvalidOperationException("Content check blocked publication: " + result.Summary);
            if (!result.Complete && OctoShipDialog.Show(this, Path.GetFileName(path) + ": " + result.Status + "\nPublish this unscanned file?", "Incomplete content scan", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) throw new OperationCanceledException("Unscanned file declined.");
        });
        _report.Text = string.Join("\n", results.Select(x => x.Url)); _status.Text = "Atomic publication confirmed.";
    }
    private async Task ValidateChannelAsync()
    {
        var repo = _repository.Text.Trim(); RepositoryWorkflowService.ValidateRepository(repo); var channel = _channel.Text.Trim().ToLowerInvariant();
        if (channel is not ("stable" or "preview")) throw new ArgumentException("Channel must be stable or preview.");
        if (_asset.Text.Trim().Length == 0) throw new ArgumentException("Enter the exact updater asset filename.");
        using var data = await GetAsync("repos/" + repo + "/releases?per_page=100");
        var release = data.RootElement.EnumerateArray().FirstOrDefault(x => !x.GetProperty("draft").GetBoolean() && x.GetProperty("prerelease").GetBoolean() == (channel == "preview"));
        if (release.ValueKind == JsonValueKind.Undefined) throw new InvalidOperationException("No matching published channel found among the latest 100 releases.");
        var tag = release.GetProperty("tag_name").GetString(); var matches = release.GetProperty("assets").EnumerateArray().Where(x => x.GetProperty("name").GetString() == _asset.Text.Trim()).ToArray();
        _report.Text = $"Repository: {repo}\nChannel: {channel}\nSelected tag: {tag}\nExpected tag: {(_version.Text.Length == 0 ? "not supplied" : _version.Text)}\nAsset: {_asset.Text}\nResult: {(matches.Length == 1 ? "asset found" : "asset missing or ambiguous")}";
        if (_version.Text.Length > 0 && tag?.TrimStart('v') != _version.Text.TrimStart('v')) _report.Text += "\nWARNING: tag differs from expected version.";
        if (matches.Length == 1) _report.Text += "\nDownload: " + matches[0].GetProperty("browser_download_url").GetString();
    }
    private void SavePlan()
    {
        _grid.CommitEdit(DataGridEditingUnit.Cell, true); _grid.CommitEdit(DataGridEditingUnit.Row, true);
        if (_selectiveStaged && _selectiveMapping != null && _mappings.Contains(_selectiveMapping)) throw new InvalidOperationException("Selective plans require a fresh remote baseline and cannot be saved. Save a regular file plan before selecting changes.");
        var d = new Microsoft.Win32.SaveFileDialog { Filter = "OctoShip preparation plan|*.json" }; if (d.ShowDialog(this) != true) return;
        File.WriteAllText(d.FileName, JsonSerializer.Serialize(new { Repository = _repository.Text, Branch = _branch.Text, Project = _root.Text, Files = _mappings }, new JsonSerializerOptions { WriteIndented = true }));
        _status.Text = "Offline plan saved without credentials. Local file paths are included; keep the plan private.";
    }
    private void LoadPlan()
    {
        var d = new Microsoft.Win32.OpenFileDialog { Filter = "OctoShip preparation plan|*.json" }; if (d.ShowDialog(this) != true) return;
        if (new FileInfo(d.FileName).Length > 1024 * 1024) throw new IOException("Plan exceeds 1 MiB.");
        using var json = JsonDocument.Parse(SecurityBoundaries.ReadBoundedJson(d.FileName, 1024 * 1024)); var r = json.RootElement;
        var files = JsonSerializer.Deserialize<List<Mapping>>(r.GetProperty("Files").GetRawText()) ?? new();
        if (files.Count > 100) throw new IOException("Plan exceeds 100 files.");
        foreach (var file in files) { if (file == null || !Path.IsPathFullyQualified(file.Source)) throw new IOException("Plan source paths must be absolute."); SecurityBoundaries.RequireRegularPath(file.Source); file.Source = Path.GetFullPath(file.Source); file.Destination = UploadQueueItem.NormalizeDestination(file.Destination); }
        _mappings.Clear(); foreach (var file in files) _mappings.Add(file);
        _repository.Text = r.GetProperty("Repository").GetString(); _branch.Text = r.GetProperty("Branch").GetString(); _root.Text = r.GetProperty("Project").GetString(); _selectiveHead = null; _selectiveStaged = false; _selectiveMapping = null; LoadProfile();
        _status.Text = "Offline plan loaded. Review local sources and destinations before publishing.";
    }
    private static StackPanel Tab(TabControl tabs, string title) { var panel = new StackPanel { Margin = new Thickness(12), Background = Brushes.White }; tabs.Items.Add(new TabItem { Header = title, Content = panel }); return panel; }
    private static void Note(Panel panel, string text) => panel.Children.Add(new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap, Foreground = Brushes.Black, Margin = new Thickness(0, 5, 0, 5) });
    private static void Field(Panel panel, string label, TextBox input, string value) { panel.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 5, 0, 3), Foreground = panel.Background == Brushes.White ? Brushes.Black : Brushes.WhiteSmoke }); input.Text = value; input.Foreground = Brushes.Black; input.Background = Brushes.White; input.Padding = new Thickness(5); panel.Children.Add(input); }
    private void Button(Panel panel, string label, Action action) { var button = new Button { Content = label, HorizontalAlignment = HorizontalAlignment.Left, Padding = new Thickness(10, 5, 10, 5), Margin = new Thickness(0, 5, 0, 5), Foreground = Brushes.Black }; button.Click += (_, _) => { if (!_busy) RunLocal(action); }; panel.Children.Add(button); }
    private void RunLocal(Action action) { try { action(); } catch (Exception ex) { _status.Text = ex.Message; } }
    private void AsyncButton(Panel panel, string label, Func<Task> action) { var button = new Button { Content = label, HorizontalAlignment = HorizontalAlignment.Left, Padding = new Thickness(10, 5, 10, 5), Margin = new Thickness(0, 5, 0, 5), Foreground = Brushes.Black }; button.Click += async (_, _) => { if (_busy) return; _busy = true; var operationContent = (UIElement)Content; operationContent.IsEnabled = false; _status.Text = "Working..."; try { await action(); } catch (Exception ex) { _status.Text = ex.Message; } finally { _busy = false; operationContent.IsEnabled = true; } }; panel.Children.Add(button); }
}
