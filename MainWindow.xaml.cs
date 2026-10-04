using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO.Compression;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.NetworkInformation;
using System.Text;
using System.Text.Json;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace FileToGitHub;

public partial class MainWindow : Window
{
    private const long MaxUploadBytes = 50L * 1024 * 1024;
    private const string DefaultUpdateRepository = "ghostventure/OctoCat";
    private static readonly Regex RepositoryPattern = new("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", RegexOptions.Compiled);
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromMinutes(3) };
    private readonly HttpClient _updateHttp = new() { Timeout = TimeSpan.FromMinutes(2) };
    private CancellationTokenSource? _uploadCancellation;
    private CancellationTokenSource? _searchCancellation;
    private readonly SearchService _searchService = new();
    private readonly GitHubRepositoryService _repositoryService;
    private UploadQueueService? _uploadQueue;
    private readonly Dictionary<string, string?> _queueExistingShas = new(StringComparer.Ordinal);
    private string _queuedDestinationFolder = string.Empty;
    private string? _token;
    private string? _account;
    private bool _busy;
    private bool _loadingAccounts = true;
    private bool _branchManuallyEdited;
    private bool _pathManuallyEdited;
    private bool _autoConnect = true;
    private string? _preferredAccount;
    private string _updateRepository = DefaultUpdateRepository;
    private bool _checkingForUpdates;
    private readonly List<string> _searchHistory = new();
    private readonly List<string> _destinationHistory = new();
    private OctoCatPreferences _appPreferences = new();
    private string[] _sensitivePatterns = Array.Empty<string>();
    private List<DestinationPreset> _namedPresets = new();
    private readonly List<GitHubProjectChoice> _githubProjects = new();
    private readonly List<string> _transferLog = new();

    public MainWindow()
    {
        InitializeComponent();
        _repositoryService = new GitHubRepositoryService(_http);
        _loadingAccounts = false;
        ResultsList.ItemsSource = _results;
        SortPicker.SelectedIndex = 0;
        ResultLimitPicker.SelectedIndex = 2;
        SearchModePicker.SelectedIndex = 0;
        UpdateExactMatchAvailability();
        BranchBox.TextChanged += (_, _) => { if (!_loadingAccounts) _branchManuallyEdited = true; };
        PathBox.TextChanged += (_, _) => { if (!_loadingAccounts) _pathManuallyEdited = true; };
        VersionLabel.Text = $"Version {GetCurrentVersion()}";
        Closed += (_, _) => { _searchCancellation?.Cancel(); _uploadCancellation?.Cancel(); _http.Dispose(); _updateHttp.Dispose(); _token = null; };
    }

    private readonly List<ResultItem> _results = new();

    private void Browse_Click(object sender, RoutedEventArgs e)
    {
        using var dialog = new System.Windows.Forms.FolderBrowserDialog { Description = "Choose the folder to search", UseDescriptionForTitle = true };
        if (dialog.ShowDialog() == System.Windows.Forms.DialogResult.OK)
        {
            SetSearchFolder(dialog.SelectedPath);
            SetStatus("Folder selected. Search by part of a file name.");
        }
    }

    private async void Search_Click(object sender, RoutedEventArgs e)
    {
        var root = FolderBox.Text;
        var query = SearchBox.Text.Trim();
        if (!Directory.Exists(root) || root.StartsWith("Choose a folder", StringComparison.Ordinal)) { SetStatus("Choose an existing folder first.", true); return; }
        if (query.Length == 0 || (query.Length < 2 && SearchModePicker.SelectedIndex == 0 && ExactMatchCheck.IsChecked != true)) { SetStatus("Enter at least two characters, or enable Exact name for a one-character filename.", true); return; }
        SearchConfiguration configuration;
        try { configuration = BuildFileSearchOptions(query, root); }
        catch (InvalidOperationException ex) { SetStatus(ex.Message, true); return; }
        RememberSearch(query);
        SaveSettings();
        _searchCancellation?.Dispose();
        _searchCancellation = new CancellationTokenSource();
        var token = _searchCancellation.Token;
        SearchButton.IsEnabled = false; CancelSearchButton.Visibility = Visibility.Visible; CancelSearchButton.IsEnabled = true;
        var progress = new Progress<SearchProgress>(value =>
        {
            ResultCount.Text = $"Scanning {value.VisitedEntries:N0} entries · {value.MatchesFound:N0} matches";
        });
        SetStatus("Searching files…");
        try
        {
            var page = await Task.Run(async () => await _searchService.SearchAsync(configuration.Options, progress, token));
            var found = page.Items.Select(item => new ResultItem(item.FullPath, item.Size, item.LastModified, item.LastModifiedUtc)).ToList();
            found = configuration.SortBy switch
            {
                SearchSort.Largest => found.OrderByDescending(r => r.Size).ThenBy(r => r.Name, StringComparer.OrdinalIgnoreCase).ToList(),
                SearchSort.Newest => found.OrderByDescending(r => r.LastModified).ThenBy(r => r.Name, StringComparer.OrdinalIgnoreCase).ToList(),
                SearchSort.Oldest => found.OrderBy(r => r.LastModified).ThenBy(r => r.Name, StringComparer.OrdinalIgnoreCase).ToList(),
                _ => found.OrderBy(r => r.Name, StringComparer.OrdinalIgnoreCase).ToList()
            };
            _results.Clear(); _results.AddRange(found);
            ResultsList.Items.Refresh(); ResultCount.Text = $"{found.Count} file{(found.Count == 1 ? "" : "s")} found" + (page.Limited ? " · scan limit reached" : "");
            ResultsList.SelectedItem = null;
            SetStatus(found.Count == 0 ? "No files matched. Try another search." : $"Choose a result to review it. {page.InaccessibleEntries} inaccessible item(s) were skipped.");
        }
        catch (OperationCanceledException) { SetStatus("Search canceled."); }
        catch (Exception ex) { SetStatus($"Search could not finish: {SafeMessage(ex)}", true); }
        finally { SearchButton.IsEnabled = true; CancelSearchButton.Visibility = Visibility.Collapsed; CancelSearchButton.IsEnabled = false; _searchCancellation?.Dispose(); _searchCancellation = null; }
    }

    private void CancelSearch_Click(object sender, RoutedEventArgs e) => _searchCancellation?.Cancel();

    private void Results_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        var item = ResultsList.SelectedItem as ResultItem;
        OpenFileButton.IsEnabled = RevealFileButton.IsEnabled = CopyPathButton.IsEnabled = CopyHashButton.IsEnabled = ReviewFileButton.IsEnabled = item is not null;
        if (item is null) { UploadButton.IsEnabled = false; SelectedFileLabel.Text = "Select one search result to review it here."; return; }
        if (!_pathManuallyEdited || string.IsNullOrWhiteSpace(PathBox.Text))
        {
            _loadingAccounts = true; PathBox.Text = item.Name; _loadingAccounts = false;
        }
        SelectedFileLabel.Text = $"{item.FullPath}\n{FormatSize(item.Size)}  ·  Modified {item.LastModified:yyyy-MM-dd HH:mm}";
        UploadButton.IsEnabled = !_busy && _token is not null;
    }

    private SearchConfiguration BuildFileSearchOptions(string query, string root)
    {
        static decimal? ParseMegabytes(string value, string label)
        {
            if (string.IsNullOrWhiteSpace(value)) return null;
            if (!decimal.TryParse(value, out var result) || result < 0 || result > 1024 * 1024)
                throw new InvalidOperationException($"{label} must be a number between 0 and 1,048,576 MB.");
            return result;
        }
        var min = ParseMegabytes(MinSizeBox.Text, "Minimum size");
        var max = ParseMegabytes(MaxSizeBox.Text, "Maximum size");
        if (min.HasValue && max.HasValue && min > max) throw new InvalidOperationException("Minimum size cannot be larger than maximum size.");
        DateTime? modified = null;
        if (!string.IsNullOrWhiteSpace(ModifiedAfterBox.Text))
        {
            if (!DateTime.TryParseExact(ModifiedAfterBox.Text.Trim(), "yyyy-MM-dd", null, System.Globalization.DateTimeStyles.None, out var parsed))
                throw new InvalidOperationException("Modified-after date must use YYYY-MM-DD format.");
            modified = parsed.Date;
        }
        var extensions = ExtensionFilterBox.Text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(ext => ext.StartsWith('.') ? ext : "." + ext).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        var excluded = ExcludedFoldersBox.Text.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries).ToList();
        var maxResults = int.TryParse((ResultLimitPicker.SelectedItem as ComboBoxItem)?.Content?.ToString(), out var parsedLimit) ? parsedLimit : 200;
        var sort = SortPicker.SelectedIndex switch { 1 => SearchSort.Largest, 2 => SearchSort.Newest, 3 => SearchSort.Oldest, _ => SearchSort.Name };
        var mode = SearchModePicker.SelectedIndex switch { 1 => SearchQueryMode.RegularExpression, 2 => SearchQueryMode.FileContents, _ => SearchQueryMode.FileName };
        if (mode == SearchQueryMode.FileContents && (ExactMatchCheck.IsChecked == true))
            throw new InvalidOperationException("Exact name applies only to filename searches; turn it off for content search.");
        var options = new global::FileToGitHub.SearchOptions(new[] { root }, query, mode, ExactMatchCheck.IsChecked == true, CaseSensitiveCheck.IsChecked == true,
            RecursiveCheck.IsChecked == true, IncludeHiddenCheck.IsChecked == true, extensions, excluded,
            min.HasValue ? (long?)(min.Value * 1024m * 1024m) : null,
            max.HasValue ? (long?)(max.Value * 1024m * 1024m) : null, modified, maxResults, MaxVisitedEntries: 100_000, MaxContentBytes: 2 * 1024 * 1024);
        return new SearchConfiguration(options, sort);
    }

    private void ClearFilters_Click(object sender, RoutedEventArgs e)
    {
        ExactMatchCheck.IsChecked = false; CaseSensitiveCheck.IsChecked = false; RecursiveCheck.IsChecked = true; IncludeHiddenCheck.IsChecked = false;
        SearchModePicker.SelectedIndex = 0;
        ExtensionFilterBox.Clear(); MinSizeBox.Clear(); MaxSizeBox.Clear(); ModifiedAfterBox.Clear(); ExcludedFoldersBox.Clear();
        SortPicker.SelectedIndex = 0; ResultLimitPicker.SelectedIndex = 2;
        SetStatus("Search filters reset to defaults.");
    }

    private void SearchModePicker_SelectionChanged(object sender, SelectionChangedEventArgs e) => UpdateExactMatchAvailability();

    private void UpdateExactMatchAvailability()
    {
        if (ExactMatchCheck is not null) ExactMatchCheck.IsEnabled = SearchModePicker.SelectedIndex == 0;
        if (SearchModePicker.SelectedIndex != 0 && ExactMatchCheck is not null) ExactMatchCheck.IsChecked = false;
    }

    private void SetSearchFolder(string folder)
    {
        FolderBox.Text = folder;
        _results.Clear(); ResultsList.Items.Refresh(); ResultsList.SelectedItem = null;
        ResultCount.Text = "Ready to search";
        SelectedFileLabel.Text = "Select one search result to review it here.";
        OpenFileButton.IsEnabled = RevealFileButton.IsEnabled = CopyPathButton.IsEnabled = CopyHashButton.IsEnabled = false;
        _loadingAccounts = true; PathBox.Clear(); _loadingAccounts = false; _pathManuallyEdited = false;
        UploadButton.IsEnabled = false;
        SaveSettings();
    }

    private void RememberSearch(string query)
    {
        if (_appPreferences.PrivacyMode) return;
        _searchHistory.RemoveAll(item => string.Equals(item, query, StringComparison.OrdinalIgnoreCase));
        _searchHistory.Insert(0, query);
        if (_searchHistory.Count > 12) _searchHistory.RemoveAt(_searchHistory.Count - 1);
        SearchBox.ItemsSource = null;
        SearchBox.ItemsSource = _searchHistory;
        SearchBox.Text = query;
    }

    private void Window_DragOver(object sender, DragEventArgs e)
    {
        e.Effects = e.Data.GetDataPresent(DataFormats.FileDrop) ? DragDropEffects.Copy : DragDropEffects.None;
        e.Handled = true;
    }

    private void Window_Drop(object sender, DragEventArgs e)
    {
        e.Handled = true;
        if (e.Data.GetData(DataFormats.FileDrop) is not string[] paths || paths.Length == 0) return;
        var path = paths[0];
        if (Directory.Exists(path))
        {
            SetSearchFolder(path);
            SetStatus("Folder dropped. Enter a filename and search.");
        }
        else if (File.Exists(path))
        {
            SetSearchFolder(Path.GetDirectoryName(path)!);
            SearchBox.Text = Path.GetFileName(path);
            var info = new FileInfo(path);
            _results.Add(new ResultItem(path, info.Length, info.LastWriteTime, info.LastWriteTimeUtc));
            ResultsList.Items.Refresh(); ResultsList.SelectedIndex = 0;
            ResultCount.Text = "1 file dropped";
            SetStatus(paths.Length > 1 ? "First dropped file ready. Other dropped items were ignored." : "File ready. Review its GitHub destination, then send it.");
        }
    }

    private ResultItem? SelectedResult => ResultsList.SelectedItem as ResultItem;
    private void OpenFile_Click(object sender, RoutedEventArgs e)
    {
        try { if (SelectedResult is { } item) Process.Start(new ProcessStartInfo(item.FullPath) { UseShellExecute = true }); }
        catch (Exception ex) { SetStatus($"Could not open the file: {SafeMessage(ex)}", true); }
    }
    private void RevealFile_Click(object sender, RoutedEventArgs e)
    {
        try { if (SelectedResult is { } item) Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{item.FullPath}\"") { UseShellExecute = true }); }
        catch (Exception ex) { SetStatus($"Could not show the file in Explorer: {SafeMessage(ex)}", true); }
    }
    private void CopyPath_Click(object sender, RoutedEventArgs e)
    {
        try { if (SelectedResult is { } item) { Clipboard.SetText(item.FullPath); SetStatus("Full file path copied."); } }
        catch (Exception ex) { SetStatus($"Could not copy the path: {SafeMessage(ex)}", true); }
    }

    private async void CopyHash_Click(object sender, RoutedEventArgs e)
    {
        if (SelectedResult is not { } item) return;
        CopyHashButton.IsEnabled = false;
        try
        {
            SetStatus("Calculating SHA-256…");
            var hash = await Task.Run(() =>
            {
                using var stream = File.OpenRead(item.FullPath);
                using var sha = SHA256.Create();
                return Convert.ToHexString(sha.ComputeHash(stream));
            });
            Clipboard.SetText(hash);
            SetStatus($"SHA-256 copied: {hash}");
        }
        catch (Exception ex) { SetStatus($"Could not calculate hash: {SafeMessage(ex)}", true); }
        finally { CopyHashButton.IsEnabled = SelectedResult is not null; }
    }

    private async void ReviewFile_Click(object sender, RoutedEventArgs e)
    {
        if (SelectedResult is not { } item) return;
        Func<string, CancellationToken, Task<string?>>? remoteLoader = null;
        if (!string.IsNullOrWhiteSpace(_token) && RepositoryPattern.IsMatch(RepoPicker.Text.Trim())
            && !string.IsNullOrWhiteSpace(BranchBox.Text))
            remoteLoader = LoadRemoteTextForReviewAsync;
        var review = new FileReviewWindow(item.FullPath, PathBox.Text.Trim(), remoteLoader, new FileSafetyRules(_sensitivePatterns)) { Owner = this };
        var proceed = review.ShowDialog() == true;
        SetStatus(proceed ? "Review complete. Check the destination, then choose Send selected file." : "File review closed.");
        await Task.CompletedTask;
    }

    private async Task<string?> LoadRemoteTextForReviewAsync(string destinationPath, CancellationToken cancellationToken)
    {
        var repository = RepoPicker.Text.Trim();
        var identity = repository.Split('/', 2);
        var branch = BranchBox.Text.Trim();
        var path = destinationPath.Replace('\\', '/').TrimStart('/');
        if (identity.Length != 2 || !IsSafePath(path)) throw new InvalidOperationException("Set a valid repository file destination before comparing versions.");
        var target = await _repositoryService.GetTargetFileAsync(identity[0], identity[1], branch, path, _token!, cancellationToken);
        if (!target.Exists) return null;
        if (target.Size > 2 * 1024 * 1024) throw new InvalidOperationException("The remote file is larger than the 2 MiB comparison limit.");
        var encodedPath = string.Join("/", path.Split('/').Select(Uri.EscapeDataString));
        using var response = await SendAsync(HttpMethod.Get,
            $"https://api.github.com/repos/{repository}/contents/{encodedPath}?ref={Uri.EscapeDataString(branch)}", _token!, cancellationToken: cancellationToken);
        await EnsureSuccess(response);
        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        if (!document.RootElement.TryGetProperty("content", out var contentElement) || contentElement.ValueKind != JsonValueKind.String)
            throw new InvalidOperationException("GitHub did not return the remote file contents for comparison.");
        var base64 = contentElement.GetString()!.Replace("\n", string.Empty, StringComparison.Ordinal).Replace("\r", string.Empty, StringComparison.Ordinal);
        var bytes = Convert.FromBase64String(base64);
        if (bytes.Length > 2 * 1024 * 1024) throw new InvalidOperationException("The remote file is larger than the 2 MiB comparison limit.");
        return new UTF8Encoding(false, false).GetString(bytes);
    }

    private async void Window_Loaded(object sender, RoutedEventArgs e)
    {
        ShowUpdateFailureIfPresent();
        var saved = ReadSavedSettings();
        _appPreferences = ReadAppPreferences();
        ReadSafetyAndPresetSettings();
        _preferredAccount = saved.Account;
        _autoConnect = saved.AutoConnect;
        _updateRepository = DefaultUpdateRepository;
        _searchHistory.AddRange(_appPreferences.PrivacyMode ? Array.Empty<string>() : _appPreferences.SearchHistory.Count > 0 ? _appPreferences.SearchHistory : saved.SearchHistory);
        _destinationHistory.AddRange(_appPreferences.Destinations.Count > 0 ? _appPreferences.Destinations : saved.Destinations);
        if (_namedPresets.Count == 0) _namedPresets = _destinationHistory.Select(value => new DestinationPreset(value, value)).ToList();
        SearchBox.ItemsSource = _searchHistory;
        DestinationPicker.ItemsSource = _namedPresets.Select(x => x.Label == x.Value ? x.Value : x.Label + "  ·  " + x.Value).ToList();
        if (!_appPreferences.PrivacyMode && !string.IsNullOrWhiteSpace(saved.LastFolder) && Directory.Exists(saved.LastFolder)) FolderBox.Text = saved.LastFolder;
        await RefreshAccountsAsync(autoConnect: _autoConnect);
        if (!string.IsNullOrWhiteSpace(_updateRepository)) _ = CheckForUpdatesAsync(silent: true);
    }

    private void AccountPicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_loadingAccounts) return;
        _token = null; _account = null;
        _githubProjects.Clear();
        RefreshGithubProjectsList();
        GithubProjectStatus.Text = "Connect an account to list its existing repositories.";
        _loadingAccounts = true;
        RepoPicker.ItemsSource = null; RepoPicker.Text = "";
        _branchManuallyEdited = false; BranchBox.Text = "main";
        _loadingAccounts = false;
        AccountLabel.Text = AccountPicker.SelectedItem is string selected ? $"{selected} selected · press Use account" : "Not connected";
        AccountLabel.Foreground = new SolidColorBrush(Color.FromRgb(158, 172, 198));
        UploadButton.IsEnabled = false;
        ConnectButton.IsEnabled = !_busy && AccountPicker.SelectedItem is string;
    }

    private async void Connect_Click(object sender, RoutedEventArgs e) => await ConnectSelectedAsync();

    private async Task ConnectSelectedAsync()
    {
        if (AccountPicker.SelectedItem is not string requestedAccount)
        {
            SetStatus("Choose a saved GitHub account, or add an account first.", true);
            return;
        }
        SetBusy(true, $"Connecting to GitHub as {requestedAccount}…");
        try
        {
            var credential = await GetCredentialAsync(requestedAccount);
            _token = credential.Token;
            if (!string.Equals(credential.Username, requestedAccount, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("Git Credential Manager returned a different account. Choose that account from the list and try again.");
            using var response = await SendAsync(HttpMethod.Get, "https://api.github.com/user", _token);
            await EnsureSuccess(response);
            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            _account = doc.RootElement.GetProperty("login").GetString();
            if (!string.Equals(_account, requestedAccount, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("GitHub returned a different account than the one selected. The upload session was stopped.");
            _preferredAccount = requestedAccount;
            _autoConnect = true;
            SaveAccountSettings(requestedAccount, autoConnect: true);
            AccountLabel.Text = _account ?? "Connected";
            AccountLabel.Foreground = new SolidColorBrush(Color.FromRgb(95, 225, 177));
            await LoadRepositoriesAsync(_token);
            SetStatus($"Connected as {_account}. Choose a repository, or type owner/name.");
        }
        catch (Exception ex)
        {
            _token = null; _account = null; AccountLabel.Text = "Not connected";
            SetStatus(SafeMessage(ex), true);
        }
        finally { SetBusy(false); }
    }

    private async void AddAccount_Click(object sender, RoutedEventArgs e)
    {
        var confirm = MessageBox.Show(this,
            "OctoShip for GitHub will open Git Credential Manager’s sign-in in your browser. Sign in to the account you want to add, then return here. Your current connection stays available until you switch accounts.",
            "Add a GitHub account", MessageBoxButton.OKCancel, MessageBoxImage.Information);
        if (confirm != MessageBoxResult.OK) return;
        SetBusy(true, "Complete GitHub sign-in in the browser or Credential Manager window…");
        try
        {
            var before = await ListGitHubAccountsAsync();
            var start = new ProcessStartInfo("git") { UseShellExecute = false, CreateNoWindow = false, WindowStyle = ProcessWindowStyle.Normal };
            foreach (var argument in new[] { "credential-manager", "github", "login", "--url", "https://github.com", "--browser", "--force" }) start.ArgumentList.Add(argument);
            start.Environment["GCM_INTERACTIVE"] = "always";
            using var process = Process.Start(start) ?? throw new InvalidOperationException("Git Credential Manager did not start.");
            await process.WaitForExitAsync();
            if (process.ExitCode != 0) throw new InvalidOperationException("GitHub sign-in did not complete. Your current account is unchanged; you can try again.");
            var after = await ListGitHubAccountsAsync();
            var newlyAdded = after.FirstOrDefault(name => !before.Contains(name, StringComparer.OrdinalIgnoreCase));
            await RefreshAccountsAsync(newlyAdded);
            if (newlyAdded is not null)
            {
                SetStatus($"Added {newlyAdded}. Connecting to that account…");
                await ConnectSelectedAsync();
            }
            else SetStatus("Sign-in completed. Select an account from the list and choose Use account.");
        }
        catch (Exception ex) { SetStatus(SafeMessage(ex), true); }
        finally { SetBusy(false); }
    }

    private void SignOut_Click(object sender, RoutedEventArgs e)
    {
        _token = null; _account = null;
        _githubProjects.Clear();
        RefreshGithubProjectsList();
        GithubProjectStatus.Text = "Signed out. Connect an account to list its repositories.";
        _autoConnect = false;
        if (AccountPicker.SelectedItem is string selectedAccount)
        {
            _preferredAccount = selectedAccount;
            SaveAccountSettings(selectedAccount, autoConnect: false);
        }
        AccountLabel.Text = "Signed out of OctoShip · saved login kept";
        AccountLabel.Foreground = new SolidColorBrush(Color.FromRgb(158, 172, 198));
        RepoPicker.ItemsSource = null; RepoPicker.Text = "";
        UploadButton.IsEnabled = false;
        SetStatus("Signed out of OctoShip. Your Windows Git Credential Manager login remains saved.");
    }

    private async Task RefreshAccountsAsync(string? prefer = null, bool autoConnect = false)
    {
        try
        {
            var accounts = await ListGitHubAccountsAsync();
            _loadingAccounts = true;
            AccountPicker.ItemsSource = accounts;
            var choice = new[] { prefer, _preferredAccount, _account, accounts.Count == 1 ? accounts[0] : null }
                .FirstOrDefault(candidate => candidate is not null && accounts.Contains(candidate, StringComparer.OrdinalIgnoreCase));
            AccountPicker.SelectedItem = choice is null ? null : accounts.First(a => string.Equals(a, choice, StringComparison.OrdinalIgnoreCase));
            _loadingAccounts = false;
            if (accounts.Count == 0)
            {
                AccountLabel.Text = "No saved GitHub accounts";
                SetStatus("Add a GitHub account to get started.");
            }
            else if (AccountPicker.SelectedItem is null)
            {
                AccountLabel.Text = $"{accounts.Count} saved accounts · choose one";
                SetStatus("Choose which GitHub account OctoShip should use.");
            }
            else if (autoConnect) await ConnectSelectedAsync();
            else AccountLabel.Text = _account ?? "Choose Use account to connect";
        }
        catch (Exception ex)
        {
            _loadingAccounts = false;
            AccountLabel.Text = "Unable to list saved accounts";
            SetStatus(SafeMessage(ex), true);
        }
    }

    private async Task<List<string>> ListGitHubAccountsAsync()
    {
        var (exitCode, output, _) = await RunGitAsync(new[] { "credential-manager", "github", "list", "--url", "https://github.com", "--no-ui" });
        if (exitCode != 0) throw new InvalidOperationException("Git Credential Manager could not list saved accounts. Check that Git for Windows is installed.");
        return output.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries)
            .Select(line => line.Trim())
            .Where(line => Regex.IsMatch(line, "^(?=.{1,39}$)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$"))
            .Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(name => name, StringComparer.OrdinalIgnoreCase).ToList();
    }

    private async Task LoadRepositoriesAsync(string token)
    {
        RepoPicker.ItemsSource = null;
        try
        {
            using var response = await SendAsync(HttpMethod.Get, "https://api.github.com/user/repos?per_page=100&sort=updated", token);
            if (!response.IsSuccessStatusCode) return;
            using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            var projects = ParseGitHubProjects(json.RootElement);
            _githubProjects.Clear(); _githubProjects.AddRange(projects);
            RefreshGithubProjectsList();
            var repositories = projects
                .Select(repo => new RepoChoice(repo.FullName, repo.DefaultBranch))
                .Where(repo => repo.FullName.Length > 0).ToList();
            RepoPicker.ItemsSource = repositories;
            SetStatus(repositories.Count == 0
                ? "Signed in. Type owner/name to choose a repository."
                : $"Signed in. Choose from {repositories.Count} recently updated repositories or type owner/name.");
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException or JsonException or InvalidOperationException)
        {
            // Repository suggestions are optional; keep sign-in active and allow manual owner/name entry.
        }
    }

    private async void LoadGithubProjects_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_token))
        {
            GithubProjectStatus.Text = "Connect a GitHub account first to list its projects.";
            return;
        }
        GithubProjectRefreshButton.IsEnabled = false;
        GithubProjectStatus.Text = "Loading existing repositories from GitHub…";
        try
        {
            var found = new List<GitHubProjectChoice>();
            for (var page = 1; page <= 20; page++)
            {
                using var response = await SendAsync(HttpMethod.Get,
                    $"https://api.github.com/user/repos?per_page=100&sort=updated&page={page}", _token);
                await EnsureSuccess(response);
                using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
                var pageItems = ParseGitHubProjects(json.RootElement);
                found.AddRange(pageItems);
                if (pageItems.Count < 100) break;
            }
            _githubProjects.Clear();
            _githubProjects.AddRange(found.GroupBy(item => item.FullName, StringComparer.OrdinalIgnoreCase).Select(group => group.First()));
            RefreshGithubProjectsList();
            GithubProjectStatus.Text = _githubProjects.Count == 0
                ? "No accessible GitHub repositories were returned for this account."
                : _githubProjects.Count >= 2000
                    ? "Showing the first 2,000 repositories. Select one, then use it as the upload destination."
                    : $"Loaded {_githubProjects.Count:N0} existing repositories. Select one, then use it as the upload destination.";
        }
        catch (Exception ex)
        {
            GithubProjectStatus.Text = "Could not load GitHub repositories: " + SafeMessage(ex);
        }
        finally { GithubProjectRefreshButton.IsEnabled = true; }
    }

    private static List<GitHubProjectChoice> ParseGitHubProjects(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Array) throw new InvalidOperationException("GitHub returned an unexpected repository list.");
        return root.EnumerateArray()
            .Where(item => item.TryGetProperty("full_name", out var name) && name.ValueKind == JsonValueKind.String
                && item.TryGetProperty("default_branch", out _))
            .Select(item =>
            {
                var updated = item.TryGetProperty("updated_at", out var time) ? time.GetString() : null;
                return new GitHubProjectChoice(
                    item.GetProperty("full_name").GetString() ?? "",
                    item.TryGetProperty("description", out var description) && description.ValueKind == JsonValueKind.String ? description.GetString() ?? "" : "",
                    item.GetProperty("default_branch").GetString() ?? "main",
                    item.TryGetProperty("private", out var isPrivate) && isPrivate.ValueKind == JsonValueKind.True,
                    updated,
                    item.TryGetProperty("html_url", out var url) && url.ValueKind == JsonValueKind.String ? url.GetString() : null);
            })
                .Where(project => RepositoryPattern.IsMatch(project.FullName))
                .ToList();
    }

    private void RefreshGithubProjectsList()
    {
        if (GithubProjectFilter is null || GithubProjectsList is null) return;
        var query = GithubProjectFilter.Text.Trim();
        var filtered = string.IsNullOrEmpty(query) ? _githubProjects : _githubProjects.Where(project =>
            project.FullName.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0
            || project.Description.IndexOf(query, StringComparison.OrdinalIgnoreCase) >= 0).ToList();
        GithubProjectsList.ItemsSource = filtered.ToArray();
        GithubProjectsList.SelectedItem = null;
        UseGithubProjectButton.IsEnabled = false;
        OpenGithubProjectButton.IsEnabled = false;
        if (_githubProjects.Count > 0)
            GithubProjectStatus.Text = $"Showing {filtered.Count():N0} of {_githubProjects.Count:N0} repositories. Search names or descriptions.";
    }

    private void GithubProjectFilter_TextChanged(object sender, TextChangedEventArgs e) => RefreshGithubProjectsList();

    private void GithubProjectsList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        var selected = GithubProjectsList.SelectedItem as GitHubProjectChoice;
        UseGithubProjectButton.IsEnabled = selected is not null;
        OpenGithubProjectButton.IsEnabled = selected is not null && Uri.TryCreate(selected.HtmlUrl, UriKind.Absolute, out var uri)
            && uri.Scheme == Uri.UriSchemeHttps && uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase);
    }

    private void UseGithubProject_Click(object sender, RoutedEventArgs e)
    {
        if (GithubProjectsList.SelectedItem is not GitHubProjectChoice project) return;
        var folder = _appPreferences.DefaultUploadFolders.TryGetValue(project.FullName, out var savedFolder) ? savedFolder : "";
        _loadingAccounts = true;
        RepoPicker.Text = project.FullName;
        BranchBox.Text = project.DefaultBranch.Length == 0 ? "main" : project.DefaultBranch;
        QueuePathBox.Text = folder;
        if (!_pathManuallyEdited)
            PathBox.Text = folder.Length == 0 ? SelectedResult?.Name ?? "" : folder.TrimEnd('/') + "/" + (SelectedResult?.Name ?? "");
        _loadingAccounts = false;
        _branchManuallyEdited = false; _pathManuallyEdited = false;
        if (!_appPreferences.PrivacyMode)
            _appPreferences = _appPreferences with { RecentRepositories = new[] { project.FullName }.Concat(_appPreferences.RecentRepositories).Distinct(StringComparer.OrdinalIgnoreCase).Take(20).ToArray() };
        SaveSettings(); UpdateReadOnlyProfile();
        GithubProjectStatus.Text = $"{project.FullName} selected as the upload target. Check the branch and path before uploading.";
    }

    private void OpenGithubProject_Click(object sender, RoutedEventArgs e)
    {
        if (GithubProjectsList.SelectedItem is not GitHubProjectChoice project
            || !Uri.TryCreate(project.HtmlUrl, UriKind.Absolute, out var uri)
            || uri.Scheme != Uri.UriSchemeHttps || !uri.Host.Equals("github.com", StringComparison.OrdinalIgnoreCase)) return;
        Process.Start(new ProcessStartInfo(uri.ToString()) { UseShellExecute = true });
    }

    private void RepoPicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (RepoPicker.SelectedItem is not RepoChoice repo) return;
        RepoPicker.Text = repo.FullName;
        if (!_branchManuallyEdited)
        {
            _loadingAccounts = true; BranchBox.Text = repo.DefaultBranch; _loadingAccounts = false;
        }
        if (!_pathManuallyEdited && _appPreferences.DefaultUploadFolders.TryGetValue(repo.FullName, out var folder))
        { _loadingAccounts = true; PathBox.Text = folder.Length == 0 ? SelectedResult?.Name ?? "" : folder.TrimEnd('/') + "/" + (SelectedResult?.Name ?? ""); _loadingAccounts = false; }
    }

    private void SearchBox_KeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key == System.Windows.Input.Key.Enter) { e.Handled = true; Search_Click(sender, e); }
    }

    private void BranchBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_loadingAccounts) _branchManuallyEdited = true;
    }

    private void PathBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (!_loadingAccounts) _pathManuallyEdited = true;
    }

    private void SaveDestination_Click(object sender, RoutedEventArgs e)
    {
        var repository = RepoPicker.Text.Trim();
        var branch = BranchBox.Text.Trim();
        var path = PathBox.Text.Trim().Replace('\\', '/');
        if (!RepositoryPattern.IsMatch(repository) || branch.Length == 0 || branch.Length > 255 || branch.Any(char.IsControl) || !IsSafePath(path))
        {
            SetStatus("Enter a valid repository, branch, and destination path before saving.", true);
            return;
        }
        var preset = $"{repository}|{branch}|{path}";
        _destinationHistory.Remove(preset);
        _destinationHistory.Insert(0, preset);
        _namedPresets.RemoveAll(item => string.Equals(item.Value, preset, StringComparison.OrdinalIgnoreCase));
        _namedPresets.Insert(0, new DestinationPreset(preset, preset));
        if (_namedPresets.Count > 12) _namedPresets.RemoveAt(_namedPresets.Count - 1);
        if (_destinationHistory.Count > 12) _destinationHistory.RemoveAt(_destinationHistory.Count - 1);
        DestinationPicker.ItemsSource = null;
        DestinationPicker.ItemsSource = _namedPresets.Select(x => x.Label == x.Value ? x.Value : x.Label + "  ·  " + x.Value).ToList();
        DestinationPicker.SelectedItem = _namedPresets.FirstOrDefault(x => x.Value == preset) is { } namedPreset && namedPreset.Label != namedPreset.Value
            ? namedPreset.Label + "  ·  " + namedPreset.Value : preset;
        SaveSettings();
        SetStatus("Destination saved on this PC.");
    }

    private void DestinationPicker_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DestinationPicker.SelectedItem is not string preset) return;
        var named = _namedPresets.FirstOrDefault(item => string.Equals(item.Label + "  ·  " + item.Value, preset, StringComparison.Ordinal));
        if (named is not null) preset = named.Value;
        var parts = preset.Split('|', 3);
        if (parts.Length != 3) return;
        _loadingAccounts = true;
        RepoPicker.Text = parts[0]; BranchBox.Text = parts[1]; PathBox.Text = parts[2];
        _loadingAccounts = false;
        _branchManuallyEdited = false; _pathManuallyEdited = false;
        SetStatus("Saved destination loaded. Review it before sending a file.");
    }

    private (string? Account, bool AutoConnect, string? LastFolder, List<string> SearchHistory, List<string> Destinations) ReadSavedSettings()
    {
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(PreferencesPath));
            var root = doc.RootElement;
            var account = root.TryGetProperty("githubAccount", out var savedAccount) && savedAccount.ValueKind == JsonValueKind.String ? savedAccount.GetString() : null;
            var autoConnect = !root.TryGetProperty("autoConnect", out var savedAutoConnect)
                || savedAutoConnect.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
                || savedAutoConnect.GetBoolean();
            var folder = root.TryGetProperty("lastFolder", out var savedFolder) && savedFolder.ValueKind == JsonValueKind.String ? savedFolder.GetString() : null;
            var searches = ReadStringList(root, "searchHistory", 12);
            var destinations = ReadStringList(root, "destinations", 12);
            return (account, autoConnect, folder, searches, destinations);
        }
        catch { return (null, true, null, new List<string>(), new List<string>()); }
    }

    private static List<string> ReadStringList(JsonElement root, string property, int max)
    {
        if (!root.TryGetProperty(property, out var array) || array.ValueKind != JsonValueKind.Array) return new List<string>();
        return array.EnumerateArray().Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString()!)
            .Where(item => item.Length <= 500).Distinct(StringComparer.OrdinalIgnoreCase).Take(max).ToList();
    }

    private static string ProductDataDirectory
    {
        get
        {
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var current = Path.Combine(local, "OctoShipForGitHub");
            var legacy = Path.Combine(local, "OctoCat");
            try
            {
                if (Directory.Exists(legacy))
                {
                    Directory.CreateDirectory(current);
                    foreach (var name in new[] { "settings.json", "preferences.json", "update-failed.txt" })
                    {
                        var oldFile = Path.Combine(legacy, name);
                        var newFile = Path.Combine(current, name);
                        if (File.Exists(oldFile) && !File.Exists(newFile)) File.Copy(oldFile, newFile, overwrite: false);
                    }
                }
            }
            catch { /* Continue with fresh defaults if old settings cannot be copied. */ }
            return current;
        }
    }
    private static string PreferencesPath => Path.Combine(ProductDataDirectory, "settings.json");
    private static string AppPreferencesPath => Path.Combine(ProductDataDirectory, "preferences.json");

    private static OctoCatPreferences ReadAppPreferences()
    {
        try { return OctoCatPreferencesService.Normalize(JsonSerializer.Deserialize<OctoCatPreferences>(File.ReadAllText(AppPreferencesPath)) ?? new OctoCatPreferences()); }
        catch { return new OctoCatPreferences(); }
    }

    private void ReadSafetyAndPresetSettings()
    {
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(PreferencesPath));
            var root = doc.RootElement;
            if (root.TryGetProperty("sensitivePatterns", out var patterns) && patterns.ValueKind == JsonValueKind.Array)
                _sensitivePatterns = patterns.EnumerateArray().Where(x => x.ValueKind == JsonValueKind.String).Select(x => x.GetString()!).Take(100).ToArray();
            if (root.TryGetProperty("namedPresets", out var presets) && presets.ValueKind == JsonValueKind.Array)
                _namedPresets = JsonSerializer.Deserialize<List<DestinationPreset>>(presets.GetRawText()) ?? new();
        }
        catch { }
    }

    private void SaveAccountSettings(string account, bool autoConnect)
    {
        _preferredAccount = account;
        _autoConnect = autoConnect;
        SaveSettings();
    }

    private void SaveSettings()
    {
        string? temporary = null;
        try
        {
            var path = PreferencesPath;
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            var settings = new
            {
                githubAccount = _preferredAccount,
                autoConnect = _autoConnect,
                lastFolder = !_appPreferences.PrivacyMode && Directory.Exists(FolderBox.Text) ? FolderBox.Text : null,
                searchHistory = (_appPreferences.PrivacyMode ? new List<string>() : _searchHistory.Take(12).ToList()),
                destinations = _destinationHistory.Take(12).ToList(),
                sensitivePatterns = _sensitivePatterns,
                namedPresets = _namedPresets
            };
            using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None, 4096, FileOptions.WriteThrough))
            {
                JsonSerializer.Serialize(stream, settings);
                stream.Flush(true);
            }
            File.Move(temporary, path, true);
            _appPreferences = OctoCatPreferencesService.Normalize(_appPreferences with
            {
                SearchHistory = _appPreferences.PrivacyMode ? Array.Empty<string>() : _searchHistory.Take(12).ToArray(),
                Destinations = _destinationHistory.Take(12).ToArray()
            });
            OctoCatPreferencesService.Export(AppPreferencesPath, _appPreferences);
        }
        catch { /* Account selection is still active for this run; credentials are never written here. */ }
        finally { if (temporary is not null) try { File.Delete(temporary); } catch { } }
    }

    private void RepositoryTools_Click(object sender, RoutedEventArgs e)
    {
        if (string.IsNullOrWhiteSpace(_token)) { SetStatus("Connect a GitHub account before browsing repositories.", true); return; }
        var repo = RepoPicker.Text.Trim();
        var folder = repo.Length > 0 && _appPreferences.DefaultUploadFolders.TryGetValue(repo, out var savedFolder) ? savedFolder : "";
        var browser = new RepositoryToolsWindow(_http, () => _token, _appPreferences.RecentRepositories, repo, BranchBox.Text.Trim(), folder) { Owner = this };
        if (browser.ShowDialog() != true || browser.SelectedRepository is not string selectedRepo) return;
        _loadingAccounts = true;
        RepoPicker.Text = selectedRepo; BranchBox.Text = browser.SelectedBranch ?? "main";
        var chosenFolder = browser.SelectedFolder ?? "";
        PathBox.Text = chosenFolder.Length == 0 ? SelectedResult?.Name ?? "" : chosenFolder.TrimEnd('/') + "/" + (SelectedResult?.Name ?? "");
        QueuePathBox.Text = chosenFolder; _loadingAccounts = false;
        _branchManuallyEdited = false; _pathManuallyEdited = false;
        if (!_appPreferences.PrivacyMode)
            _appPreferences = _appPreferences with { RecentRepositories = new[] { selectedRepo }.Concat(_appPreferences.RecentRepositories).Distinct(StringComparer.OrdinalIgnoreCase).Take(20).ToArray() };
        if (chosenFolder.Length > 0)
        {
            var folders = new Dictionary<string, string>(_appPreferences.DefaultUploadFolders, StringComparer.OrdinalIgnoreCase) { [selectedRepo] = chosenFolder };
            _appPreferences = _appPreferences with { DefaultUploadFolders = folders };
        }
        SaveSettings(); SetStatus($"Selected {selectedRepo} · {BranchBox.Text} · {chosenFolder}");
    }

    private void ReleasePublisher_Click(object sender, RoutedEventArgs e)
    {
        var repository = RepoPicker.Text.Trim();
        if (string.IsNullOrWhiteSpace(_token) || !RepositoryPattern.IsMatch(repository))
        { SetStatus("Connect an account and select a repository before preparing a release.", true); return; }
        var parts = repository.Split('/', 2);
        new ReleasePublisherWindow(_http, parts[0], parts[1], BranchBox.Text.Trim(), _token) { Owner = this }.ShowDialog();
    }

    private async Task ValidateUploadContentAsync(string sourcePath, byte[] bytes, CancellationToken ct)
    {
        var result = await Task.Run(() => ContentSecretScanner.ScanBytes(bytes, ct), ct);
        if (!result.HasFindings && result.Complete) return;
        ct.ThrowIfCancellationRequested();
        var accepted = await Dispatcher.InvokeAsync(() => MessageBox.Show(this,
            $"Review content scan for {Path.GetFileName(sourcePath)}:\n\n{result.Summary}\n\nSecret detection is not exhaustive. Published content can remain in Git history. Continue with this file?",
            "Review content before upload", MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes);
        if (!accepted) throw new OperationCanceledException("Content review declined. Nothing further was sent.", ct);
    }

    private void ShowToolsPage_Click(object sender, RoutedEventArgs e)
        => ShowToolsPage();

    private void ShowToolsPage()
    {
        HomeView.Visibility = Visibility.Collapsed;
        ToolsView.Visibility = Visibility.Visible;
        ToolsVersionLabel.Text = VersionLabel.Text;
        ToolsAccountStatus.Text = _account is null ? "Account status: not connected" : $"Account status: connected as {_account}";
        NetworkStatus.Text = GetNetworkNotice();
        UpdateReadOnlyProfile();
    }

    private void UpdateReadOnlyProfile()
    {
        ProfileAccount.Text = _account ?? _preferredAccount ?? "Not set";
        ProfileRepository.Text = string.IsNullOrWhiteSpace(RepoPicker.Text) ? "Not selected" : RepoPicker.Text.Trim();
        ProfileChannel.Text = _appPreferences.UpdateChannel.ToString();
        ProfilePrivacy.Text = _appPreferences.PrivacyMode ? "On" : "Off";
    }

    private void BackToSearch_Click(object sender, RoutedEventArgs e)
    {
        ToolsView.Visibility = Visibility.Collapsed;
        HomeView.Visibility = Visibility.Visible;
    }

    private void OpenDataFolder_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var folder = Path.GetDirectoryName(PreferencesPath)!;
            Directory.CreateDirectory(folder);
            Process.Start(new ProcessStartInfo("explorer.exe", $"\"{folder}\"") { UseShellExecute = true });
        }
        catch (Exception ex) { MessageBox.Show(this, "Could not open the OctoShip data folder: " + SafeMessage(ex), "OctoShip for GitHub", MessageBoxButton.OK, MessageBoxImage.Warning); }
    }

    private void CheckCompatibility_Click(object sender, RoutedEventArgs e)
    {
        CompatibilityStatus.Text = "Checking Windows, runtime, and Git availability…";
        var gitPath = FindExecutableOnPath("git.exe");
        var isWindows = OperatingSystem.IsWindows();
        var is64Bit = Environment.Is64BitProcess;
        var compatible = isWindows && is64Bit && gitPath is not null;
        CompatibilityStatus.Foreground = compatible ? new SolidColorBrush(Color.FromRgb(116, 221, 168)) : new SolidColorBrush(Color.FromRgb(255, 161, 129));
        CompatibilityStatus.Text = $"{(compatible ? "Compatible" : "Check required")}: Windows {(isWindows ? "available" : "required")}; .NET {Environment.Version} active; {RuntimeInformation.ProcessArchitecture}; Git {(gitPath is null ? "not found on PATH" : "available")}. Git Credential Manager sign-in is still needed to connect.";
        NetworkStatus.Text = GetNetworkNotice();
    }

    private void CopyDiagnostics_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var report = string.Join(Environment.NewLine,
                "OctoShip for GitHub diagnostics",
                "Version: " + GetCurrentVersion(),
                "Windows: " + Environment.OSVersion.VersionString,
                "Runtime: .NET " + Environment.Version,
                "Architecture: " + RuntimeInformation.ProcessArchitecture,
                "Network: " + DetectNetwork().Name,
                "Git available: " + (FindExecutableOnPath("git.exe") is not null),
                "GitHub connected: " + (_account is not null),
                "Update channel: " + _appPreferences.UpdateChannel,
                "Privacy mode: " + _appPreferences.PrivacyMode);
            Clipboard.SetText(report);
            SetStatus("Privacy-safe diagnostics copied. No account name, token, or local file paths were included.");
        }
        catch (Exception ex) { SetStatus("Could not copy diagnostics: " + SafeMessage(ex), true); }
    }

    private static string? FindExecutableOnPath(string name)
    {
        foreach (var folder in (Environment.GetEnvironmentVariable("PATH") ?? string.Empty).Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            try { var candidate = Path.Combine(folder.Trim('"'), name); if (File.Exists(candidate)) return candidate; }
            catch { }
        }
        return null;
    }

    private static (string Name, bool Wifi) DetectNetwork()
    {
        try
        {
            var active = NetworkInterface.GetAllNetworkInterfaces()
                .Where(adapter => adapter.OperationalStatus == OperationalStatus.Up && adapter.NetworkInterfaceType != NetworkInterfaceType.Loopback)
                .ToArray();
            if (active.Length == 0) return ("No active network adapter", false);
            var withGateway = active.Where(adapter =>
            {
                try { return adapter.GetIPProperties().GatewayAddresses.Any(gateway => !gateway.Address.Equals(IPAddress.Any) && !gateway.Address.Equals(IPAddress.IPv6Any)); }
                catch { return false; }
            }).ToArray();
            var candidates = withGateway.Length > 0 ? withGateway : active;
            var wifi = candidates.Any(adapter => adapter.NetworkInterfaceType == NetworkInterfaceType.Wireless80211);
            var ethernet = candidates.Any(adapter => adapter.NetworkInterfaceType == NetworkInterfaceType.Ethernet);
            var name = wifi && ethernet ? "Wi-Fi and Ethernet" : wifi ? "Wi-Fi" : ethernet ? "Ethernet (wired)" : "Other active network";
            return (name, wifi);
        }
        catch { return ("Unknown network type", false); }
    }

    private static string GetNetworkNotice()
    {
        var network = DetectNetwork();
        return network.Wifi
            ? $"Network: {network.Name}. Wi-Fi can make uploads and downloads take longer."
            : $"Network: {network.Name}.";
    }

    private static string EstimateRemaining(TimeSpan elapsed, long transferred, long total)
    {
        if (elapsed.TotalSeconds < 1 || transferred < 16 * 1024) return "estimating remaining time";
        var bytesPerSecond = transferred / elapsed.TotalSeconds;
        if (bytesPerSecond <= 0) return "estimating remaining time";
        var remaining = TimeSpan.FromSeconds(Math.Max(0, total - transferred) / bytesPerSecond);
        var formatted = remaining.TotalHours >= 1
            ? $"{(int)remaining.TotalHours}:{remaining.Minutes:D2}:{remaining.Seconds:D2}"
            : $"{remaining.Minutes:D2}:{remaining.Seconds:D2}";
        return $"about {formatted} remaining";
    }

    private void LogTransfer(string message)
    {
        if (!Dispatcher.CheckAccess()) { Dispatcher.BeginInvoke(new Action(() => LogTransfer(message))); return; }
        _transferLog.Add($"[{DateTime.Now:HH:mm:ss}] {message}");
        if (_transferLog.Count > 400) _transferLog.RemoveRange(0, _transferLog.Count - 400);
        TransferTerminal.Text = string.Join(Environment.NewLine, _transferLog);
        TransferTerminal.ScrollToEnd();
        TerminalExpander.IsExpanded = true;
    }

    private void Settings_Click(object sender, RoutedEventArgs e)
    {
        var settings = new OctoCatSettingsWindow(_appPreferences, _sensitivePatterns, _namedPresets) { Owner = this };
        if (settings.ShowDialog() != true) return;
        _appPreferences = settings.Preferences; _sensitivePatterns = settings.SensitivePatterns.ToArray(); _namedPresets = settings.DestinationPresets.ToList();
        _destinationHistory.Clear(); _destinationHistory.AddRange(_namedPresets.Select(x => x.Value).Distinct(StringComparer.OrdinalIgnoreCase).Take(12));
        DestinationPicker.ItemsSource = _namedPresets.Select(x => x.Label + "  ·  " + x.Value).ToList();
        _searchHistory.Clear();
        if (!_appPreferences.PrivacyMode) _searchHistory.AddRange(_appPreferences.SearchHistory);
        SearchBox.ItemsSource = null; SearchBox.ItemsSource = _searchHistory;
        UpdateReadOnlyProfile();
        SaveSettings(); SetStatus("Settings saved. Privacy mode and update channel apply immediately.");
    }

    private async void Update_Click(object sender, RoutedEventArgs e) => await CheckForUpdatesAsync(silent: false);

    private async Task CheckForUpdatesAsync(bool silent)
    {
        if (_checkingForUpdates) return;
        _checkingForUpdates = true;
        UpdateButton.IsEnabled = false;
        var oldStatus = StatusLabel.Text;
        if (!silent) SetStatus("Checking OctoShip releases…");
        try
        {
            var url = _appPreferences.UpdateChannel == OctoCatUpdateChannel.Preview
                ? $"https://api.github.com/repos/{_updateRepository}/releases?per_page=20"
                : $"https://api.github.com/repos/{_updateRepository}/releases/latest";
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.4");
            request.Headers.Accept.ParseAdd("application/vnd.github+json");
            using var response = await _updateHttp.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);
            if (response.StatusCode == HttpStatusCode.NotFound)
                throw new InvalidOperationException("The update repository or its stable release could not be found. Check the owner/name and publish a stable release.");
            response.EnsureSuccessStatusCode();
            using var release = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            var selectedRelease = release.RootElement.ValueKind == JsonValueKind.Array
                ? release.RootElement.EnumerateArray().FirstOrDefault(item => item.TryGetProperty("draft", out var draft) && !draft.GetBoolean() && item.TryGetProperty("prerelease", out var prerelease) && prerelease.GetBoolean())
                : release.RootElement;
            if (_appPreferences.UpdateChannel == OctoCatUpdateChannel.Preview && selectedRelease.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("No published preview release is available. Switch to Stable to use the latest production release.");
            if (selectedRelease.ValueKind != JsonValueKind.Object) throw new InvalidOperationException("No published release is available for this update channel.");
            var tag = selectedRelease.GetProperty("tag_name").GetString() ?? string.Empty;
            var versionText = tag.TrimStart('v', 'V');
            if (!Version.TryParse(versionText, out var latest))
                throw new InvalidOperationException("The latest stable release needs a version tag such as v1.0.1.");
            var current = GetCurrentVersion();
            if (latest <= current)
            {
                if (!silent) MessageBox.Show(this, $"OctoShip for GitHub {current} is up to date.", "No updates available", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            if (!selectedRelease.TryGetProperty("assets", out var assets))
                throw new InvalidOperationException("The release has no update package. Attach OctoShip-win-x64.zip to the GitHub release.");
            var asset = assets.EnumerateArray().FirstOrDefault(item =>
                item.TryGetProperty("name", out var name) && string.Equals(name.GetString(), "OctoShip-win-x64.zip", StringComparison.OrdinalIgnoreCase));
            if (asset.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("The release needs an asset named OctoShip-win-x64.zip containing the published app files.");
            var digest = asset.TryGetProperty("digest", out var digestElement) ? digestElement.GetString() : null;
            if (digest is null || !digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("GitHub did not provide a SHA-256 asset digest. This release cannot be installed safely.");
            var downloadUrl = asset.GetProperty("browser_download_url").GetString();
            if (downloadUrl is null || !Uri.TryCreate(downloadUrl, UriKind.Absolute, out var assetUri) || assetUri.Scheme != Uri.UriSchemeHttps || assetUri.Host != "github.com")
                throw new InvalidOperationException("The release package URL is not a valid GitHub HTTPS download.");

            var install = MessageBox.Show(this,
                $"OctoShip for GitHub {latest} is available (you have {current}).\n\nInstall it now? OctoShip will download the release, verify its SHA-256 digest, close, and restart with the update.",
                "OctoShip update available", MessageBoxButton.YesNo, MessageBoxImage.Information);
            if (install != MessageBoxResult.Yes) return;
            var packageSize = asset.TryGetProperty("size", out var sizeElement) && sizeElement.ValueKind == JsonValueKind.Number && sizeElement.TryGetInt64(out var parsedSize) && parsedSize > 0
                ? parsedSize : (long?)null;
            await DownloadAndApplyUpdateAsync(assetUri, latest, digest.Substring("sha256:".Length), packageSize);
        }
        catch (Exception ex)
        {
            UpdateDownloadProgress.Visibility = Visibility.Collapsed;
            UpdateDownloadStatus.Text = "Update download failed: " + SafeMessage(ex);
            LogTransfer("Update download failed: " + SafeMessage(ex));
            if (!silent) MessageBox.Show(this, SafeMessage(ex), "Update check failed", MessageBoxButton.OK, MessageBoxImage.Warning);
            else SetStatus("Automatic update check failed. Use Check for updates to retry.", true);
        }
        finally
        {
            _checkingForUpdates = false;
            UpdateButton.IsEnabled = true;
            if (!silent && StatusLabel.Text == "Checking OctoShip releases…") SetStatus(oldStatus);
        }
    }

    private async Task DownloadAndApplyUpdateAsync(Uri assetUri, Version version, string expectedHash, long? expectedPackageSize = null)
    {
        ShowToolsPage();
        var networkNotice = GetNetworkNotice();
        NetworkStatus.Text = networkNotice;
        LogTransfer($"Starting update download for version {version}. {networkNotice}");
        UpdateDownloadProgress.Visibility = Visibility.Visible;
        UpdateDownloadProgress.Value = 0;
        UpdateDownloadStatus.Text = "Starting update download…";
        SetStatus($"Downloading OctoShip for GitHub {version}…");
        using var response = await _updateHttp.GetAsync(assetUri, HttpCompletionOption.ResponseHeadersRead);
        response.EnsureSuccessStatusCode();
        var totalLength = response.Content.Headers.ContentLength ?? expectedPackageSize;
        if (totalLength is long length && length > 250L * 1024 * 1024)
            throw new InvalidOperationException("The update package is larger than the 250 MB safety limit.");
        using var input = await response.Content.ReadAsStreamAsync();
        using var packageBuffer = new MemoryStream(totalLength is > 0 and <= int.MaxValue ? (int)totalLength.Value : 0);
        var chunk = new byte[96 * 1024];
        long received = 0;
        var downloadTimer = Stopwatch.StartNew();
        var lastLoggedPercent = -10;
        int read;
        while ((read = await input.ReadAsync(chunk.AsMemory(0, chunk.Length), CancellationToken.None)) > 0)
        {
            received += read;
            if (received > 250L * 1024 * 1024) throw new InvalidOperationException("The update package exceeded the 250 MB safety limit while downloading.");
            await packageBuffer.WriteAsync(chunk, 0, read);
            if (totalLength is > 0)
            {
                var percent = (int)Math.Clamp(received * 100L / totalLength.Value, 0L, 100L);
                UpdateDownloadProgress.IsIndeterminate = false;
                UpdateDownloadProgress.Value = percent;
                UpdateDownloadStatus.Text = $"Downloading update: {percent}% · {FormatSize(received)} of {FormatSize(totalLength.Value)} · {EstimateRemaining(downloadTimer.Elapsed, received, totalLength.Value)}. {networkNotice}";
                if (percent >= lastLoggedPercent + 10 || percent == 100)
                {
                    lastLoggedPercent = percent;
                    LogTransfer($"Downloading OctoShip update {version}: {percent}% · {EstimateRemaining(downloadTimer.Elapsed, received, totalLength.Value)}");
                }
            }
            else
            {
                UpdateDownloadProgress.IsIndeterminate = true;
                UpdateDownloadStatus.Text = $"Downloaded {FormatSize(received)} so far · ETA unavailable because package size is unknown. {networkNotice}";
            }
        }
        var archiveBytes = packageBuffer.ToArray();
        var actualHash = Convert.ToHexString(SHA256.HashData(archiveBytes));
        if (!string.Equals(actualHash, expectedHash, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("The downloaded package did not match GitHub's SHA-256 digest. Nothing was installed.");
        UpdateDownloadProgress.Visibility = Visibility.Collapsed;
        UpdateDownloadStatus.Text = "Download complete. SHA-256 verification passed.";
        LogTransfer($"Update download complete for {version}; SHA-256 verified ({FormatSize(received)}).");

        var appDirectory = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        var staging = Path.Combine(ProductDataDirectory, "updates", version.ToString(), "package");
        Directory.CreateDirectory(staging);
        var archivePath = Path.Combine(Path.GetDirectoryName(staging)!, "update.zip");
        await File.WriteAllBytesAsync(archivePath, archiveBytes);
        using (var archive = ZipFile.OpenRead(archivePath))
        {
            foreach (var entry in archive.Entries)
            {
                var destination = Path.GetFullPath(Path.Combine(staging, entry.FullName));
                if (!destination.StartsWith(staging + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
                    && !string.Equals(destination, staging, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("The update archive contains an unsafe file path.");
            }
        }
        ZipFile.ExtractToDirectory(archivePath, staging, overwriteFiles: true);
        if (!File.Exists(Path.Combine(staging, "OctoShip.exe")) || !File.Exists(Path.Combine(staging, "OctoShip.dll")))
            throw new InvalidOperationException("The release ZIP is missing OctoShip.exe or OctoShip.dll.");

        var failureMarker = Path.Combine(ProductDataDirectory, "update-failed.txt");
        var script = "$ErrorActionPreference='Stop';"
            + "$parent=" + Environment.ProcessId + ";"
            + "$src=" + PowerShellLiteral(staging) + ";"
            + "$dst=" + PowerShellLiteral(appDirectory) + ";"
            + "$marker=" + PowerShellLiteral(failureMarker) + ";"
            + "while(Get-Process -Id $parent -ErrorAction SilentlyContinue){Start-Sleep -Milliseconds 300};"
            + "try{Copy-Item -Path (Join-Path $src '*') -Destination $dst -Recurse -Force;"
            + "if(Test-Path $marker){Remove-Item $marker -Force};Start-Process (Join-Path $dst 'OctoShip.exe')}"
            + "catch{[IO.File]::WriteAllText($marker,$_.Exception.Message);Start-Process (Join-Path $dst 'OctoShip.exe')}";
        var encodedCommand = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));
        var start = new ProcessStartInfo("powershell.exe", $"-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand {encodedCommand}")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };
        _ = Process.Start(start) ?? throw new InvalidOperationException("The Windows update helper could not start.");
        SetStatus($"Update verified. Restarting into OctoShip for GitHub {version}…");
        Application.Current.Shutdown();
    }

    private static string PowerShellLiteral(string value) => "'" + value.Replace("'", "''") + "'";

    private static Version GetCurrentVersion() =>
        System.Reflection.Assembly.GetEntryAssembly()?.GetName().Version ?? new Version(1, 0, 0);

    private void ShowUpdateFailureIfPresent()
    {
        var marker = Path.Combine(ProductDataDirectory, "update-failed.txt");
        try
        {
            if (!File.Exists(marker)) return;
            var reason = File.ReadAllText(marker);
            File.Delete(marker);
            MessageBox.Show(this, $"The update could not replace the current app files. OctoShip started with the previous version.\n\n{reason}", "Update could not be installed", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
        catch { }
    }

    private static async Task<(int ExitCode, string Output, string Error)> RunGitAsync(IEnumerable<string> arguments, string? input = null)
    {
        var start = new ProcessStartInfo("git") { UseShellExecute = false, CreateNoWindow = true, RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in arguments) start.ArgumentList.Add(argument);
        start.Environment["GCM_INTERACTIVE"] = "never";
        start.Environment["GIT_TERMINAL_PROMPT"] = "0";
        using var process = Process.Start(start) ?? throw new InvalidOperationException("Git for Windows could not start.");
        var outputTask = process.StandardOutput.ReadToEndAsync();
        var errorTask = process.StandardError.ReadToEndAsync();
        if (input is not null) await process.StandardInput.WriteAsync(input);
        process.StandardInput.Close();
        await process.WaitForExitAsync();
        return (process.ExitCode, await outputTask, await errorTask);
    }

    private async void Upload_Click(object sender, RoutedEventArgs e)
    {
        if (ResultsList.SelectedItem is not ResultItem selected) { SetStatus("Select a file from the search results first.", true); return; }
        if (string.IsNullOrWhiteSpace(_token) || string.IsNullOrWhiteSpace(_account)) { SetStatus("Connect your signed-in GitHub account first.", true); return; }
        var repository = RepoPicker.Text.Trim();
        var branch = BranchBox.Text.Trim();
        var targetPath = PathBox.Text.Trim().Replace('\\', '/');
        var commitMessage = CommitMessageBox.Text.Trim();
        if (!RepositoryPattern.IsMatch(repository)) { SetStatus("Enter a repository as owner/name.", true); return; }
        if (branch.Length == 0 || branch.Length > 255 || branch.Any(char.IsControl)) { SetStatus("Enter a valid branch name.", true); return; }
        if (!IsSafePath(targetPath)) { SetStatus("Enter a repository path such as uploads/report.pdf.", true); return; }
        if (commitMessage.Length is < 1 or > 250) { SetStatus("Enter a commit message between 1 and 250 characters.", true); return; }
        try
        {
            if (selected.HasChangedOnDisk()) { SetStatus("This file changed since the search. Search again and review the current version before uploading.", true); return; }
            var info = new FileInfo(selected.FullPath);
            if (!info.Exists || info.Length > MaxUploadBytes) { SetStatus("The selected file is missing or larger than 50 MB.", true); return; }
            var destination = $"https://github.com/{repository}/blob/{Uri.EscapeDataString(branch)}/{string.Join("/", targetPath.Split('/').Select(Uri.EscapeDataString))}";
            var networkNotice = GetNetworkNotice();
            var prompt = $"Send this file to GitHub?\n\nAccount: {_account}\nRepository: {repository}\nBranch: {branch}\nPath: {targetPath}\nCommit message: {commitMessage}\nLocal file: {selected.FullPath}\nSize: {FormatSize(info.Length)}\n\n{networkNotice}\n\nGitHub will record a commit on this branch.";
            if (MessageBox.Show(this, prompt, "Review upload", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
            LogTransfer($"Starting upload: {Path.GetFileName(selected.FullPath)} → {repository}/{targetPath} ({FormatSize(info.Length)}). {networkNotice}");
            if (LooksSensitive(selected.Name) || LooksSensitive(Path.GetFileName(targetPath)))
            {
                var warning = "This filename is commonly used for credentials or private keys. GitHub commits can remain in repository history after deletion.\n\nUpload this file anyway?";
                if (MessageBox.Show(this, warning, "Possible secret file", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
            }

            var cancellation = new CancellationTokenSource();
            _uploadCancellation = cancellation;
            CancelUploadButton.Visibility = Visibility.Visible;
            CancelUploadButton.IsEnabled = true;
            UploadProgress.Visibility = Visibility.Visible;
            UploadProgress.IsIndeterminate = true;
            UploadProgress.Value = 0;
            SetBusy(true, "Checking the GitHub destination…");
            var encodedPath = string.Join("/", targetPath.Split('/').Select(Uri.EscapeDataString));
            var baseUrl = $"https://api.github.com/repos/{repository}";
            var token = cancellation.Token;
            var identity = repository.Split('/', 2);
            var repositoryInfo = await _repositoryService.GetRepositoryAsync(identity[0], identity[1], _token, token);
            if (repositoryInfo.Archived || repositoryInfo.Disabled)
                throw new InvalidOperationException("This repository is archived or disabled, so OctoShip will not upload to it.");
            if (repositoryInfo.CanPush == false)
                throw new InvalidOperationException("GitHub confirms that this account cannot push to this repository.");
            if (repositoryInfo.CanPush is null && MessageBox.Show(this,
                    "GitHub did not report whether this account can push to the repository. Continue with the normal destination checks?",
                    "Write access could not be confirmed", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
                return;
            using (var branchResponse = await SendAsync(HttpMethod.Get, $"{baseUrl}/branches/{Uri.EscapeDataString(branch)}", _token, cancellationToken: token)) await EnsureSuccess(branchResponse);

            string? existingSha = null;
            using (var existing = await SendAsync(HttpMethod.Get, $"{baseUrl}/contents/{encodedPath}?ref={Uri.EscapeDataString(branch)}", _token, cancellationToken: token))
            {
            if (existing.StatusCode == HttpStatusCode.OK)
                {
                    using var doc = JsonDocument.Parse(await existing.Content.ReadAsStringAsync(token));
                    if (doc.RootElement.TryGetProperty("type", out var type) && type.GetString() != "file") throw new InvalidOperationException("That destination is a directory. Choose a file path.");
                    existingSha = doc.RootElement.GetProperty("sha").GetString();
                    var overwrite = MessageBox.Show(this, $"The destination already exists. Replace it with {selected.Name}?\n\n{destination}", "Confirm replacement", MessageBoxButton.YesNo, MessageBoxImage.Warning);
                    if (overwrite != MessageBoxResult.Yes) { SetStatus("Upload cancelled. The existing GitHub file was left unchanged."); return; }
                }
                else if (existing.StatusCode != HttpStatusCode.NotFound) await EnsureSuccess(existing);
            }

            SetStatus("Reading the selected file…");
            var bytes = await ReadStableFileAsync(selected.FullPath, selected.Size, selected.LastWriteTimeUtc, token);
            await ValidateUploadContentAsync(selected.FullPath, bytes, token);
            if (bytes.LongLength > MaxUploadBytes) throw new InvalidOperationException("The file grew larger than the 50 MB upload limit. Nothing was sent.");
            LogTransfer($"Sending {Path.GetFileName(selected.FullPath)} to {repository}/{targetPath} · {FormatSize(bytes.Length)} via {DetectNetwork().Name}.");
            SetStatus("Uploading 0%…");
            UploadProgress.IsIndeterminate = false;
            var lastPercent = -1;
            var lastLoggedPercent = -10;
            var uploadTimer = Stopwatch.StartNew();
            var progress = new Progress<double>(value =>
            {
                var percent = (int)Math.Round(value * 100);
                UploadProgress.Value = percent;
                var transferred = (long)(bytes.LongLength * Math.Clamp(value, 0, 1));
                if (percent != lastPercent) { lastPercent = percent; SetStatus($"Uploading {percent}% · {EstimateRemaining(uploadTimer.Elapsed, transferred, bytes.LongLength)}"); }
                if (percent >= lastLoggedPercent + 10 || percent == 100) { lastLoggedPercent = percent; LogTransfer($"Uploading {repository}/{targetPath}: {percent}% · {EstimateRemaining(uploadTimer.Elapsed, transferred, bytes.LongLength)}"); }
            });
            using var content = new UploadJsonContent(bytes, commitMessage, branch, existingSha, progress);
            using var response = await SendAsync(HttpMethod.Put, $"{baseUrl}/contents/{encodedPath}", _token, content, token);
            await EnsureSuccess(response);
            LogTransfer($"Upload complete: {repository}/{targetPath}.");
            using var saved = JsonDocument.Parse(await response.Content.ReadAsStringAsync(token));
            var url = saved.RootElement.GetProperty("content").GetProperty("html_url").GetString();
            var preset = $"{repository}|{branch}|{targetPath}";
            _destinationHistory.Remove(preset); _destinationHistory.Insert(0, preset);
            if (_destinationHistory.Count > 12) _destinationHistory.RemoveAt(_destinationHistory.Count - 1);
            DestinationPicker.ItemsSource = null; DestinationPicker.ItemsSource = _destinationHistory; SaveSettings();
            SetStatus($"Uploaded successfully to {repository}/{targetPath}. GitHub commit created.");
            if (url is not null && MessageBox.Show(this, "File uploaded successfully. Open it on GitHub?", "Upload complete", MessageBoxButton.YesNo, MessageBoxImage.Information) == MessageBoxResult.Yes)
                Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch (OperationCanceledException) { LogTransfer($"Upload canceled: {repository}/{targetPath}. Confirm GitHub state before retrying."); SetStatus("Upload canceled. If data was already sending, check GitHub before retrying; the commit may have completed.", true); }
        catch (Exception ex) { LogTransfer($"Upload failed: {repository}/{targetPath}: {SafeMessage(ex)}"); SetStatus(SafeMessage(ex), true); }
        finally
        {
            _uploadCancellation?.Dispose();
            _uploadCancellation = null;
            CancelUploadButton.Visibility = Visibility.Collapsed;
            CancelUploadButton.IsEnabled = false;
            UploadProgress.Visibility = Visibility.Collapsed;
            UploadProgress.IsIndeterminate = false;
            UploadProgress.Value = 0;
            SetBusy(false);
        }
    }

    private void CancelUpload_Click(object sender, RoutedEventArgs e) => _uploadCancellation?.Cancel();

    private void QueueFolder_Click(object sender, RoutedEventArgs e)
    {
        using var dialog = new System.Windows.Forms.FolderBrowserDialog { Description = "Choose a folder to upload, preserving its subfolder structure", UseDescriptionForTitle = true };
        if (dialog.ShowDialog() != System.Windows.Forms.DialogResult.OK) return;
        try
        {
            var destinationFolder = QueuePathBox.Text.Trim().Replace('\\', '/').Trim('/');
            var items = UploadQueuePlanner.FromFolder(dialog.SelectedPath, destinationFolder);
            if (items.Count == 0) { SetStatus("The selected folder contains no files.", true); return; }
            if (items.Count > 100) { SetStatus("A folder batch is limited to 100 files. Choose a smaller folder.", true); return; }
            _queuedDestinationFolder = destinationFolder;
            _uploadQueue = new UploadQueueService(items);
            _uploadQueue.Changed += (_, _) => Dispatcher.BeginInvoke(new Action(RefreshQueueView));
            _queueExistingShas.Clear();
            RefreshQueueView();
            QueueList.Visibility = Visibility.Visible;
            QueueStatusLabel.Text = $"{items.Count} file(s) queued · {(double)items.Sum(item => item.CapturedLength) / (1024 * 1024):0.##} MB total. Each file creates its own commit.";
            QueueRunButton.IsEnabled = _token is not null;
            QueueRetryButton.IsEnabled = false;
        }
        catch (Exception ex) { SetStatus($"Could not queue this folder: {SafeMessage(ex)}", true); }
    }

    private void RefreshQueueView()
    {
        if (!Dispatcher.CheckAccess()) { Dispatcher.BeginInvoke(new Action(RefreshQueueView)); return; }
        var items = _uploadQueue?.Items ?? Array.Empty<UploadQueueItem>();
        QueueList.ItemsSource = items.Select(item => $"{item.State,-9} {item.ProgressPercent,3:0}%  {item.DestinationPath}" + (string.IsNullOrWhiteSpace(item.Error) ? "" : $" · {item.Error}")).ToArray();
        QueueRunButton.IsEnabled = _uploadQueue is not null && !_uploadQueue.IsRunning && _token is not null && items.Any(item => item.State is UploadQueueItemState.Queued or UploadQueueItemState.Failed);
        QueuePauseButton.IsEnabled = _uploadQueue?.IsRunning == true;
        QueuePauseButton.Content = _uploadQueue?.IsPaused == true ? "Resume" : "Pause";
        QueueRetryButton.IsEnabled = _uploadQueue is not null && !_uploadQueue.IsRunning && items.Any(item => item.State is UploadQueueItemState.Failed or UploadQueueItemState.Cancelled);
    }

    private async void QueueRun_Click(object sender, RoutedEventArgs e)
    {
        if (_uploadQueue is null || string.IsNullOrWhiteSpace(_token) || string.IsNullOrWhiteSpace(_account)) { SetStatus("Connect a GitHub account and choose a folder first.", true); return; }
        var repository = RepoPicker.Text.Trim();
        var branch = BranchBox.Text.Trim();
        var message = CommitMessageBox.Text.Trim();
        var currentQueueFolder = QueuePathBox.Text.Trim().Replace('\\', '/').Trim('/');
        if (!string.Equals(currentQueueFolder, _queuedDestinationFolder, StringComparison.Ordinal))
        { SetStatus("The destination folder changed after these files were queued. Choose the local folder again to rebuild the queue.", true); return; }
        if (!RepositoryPattern.IsMatch(repository) || branch.Length == 0 || (currentQueueFolder.Length > 0 && !IsSafePath(currentQueueFolder + "/placeholder")) || message.Length is < 1 or > 250)
        { SetStatus("Check the repository, branch, destination folder, and commit message before uploading.", true); return; }
        var items = _uploadQueue.Items.Where(item => item.State is UploadQueueItemState.Queued or UploadQueueItemState.Failed).ToArray();
        if (items.Length == 0) return;
        var identity = repository.Split('/', 2);
        var cancellation = new CancellationTokenSource();
        _uploadCancellation = cancellation;
        CancelUploadButton.Visibility = Visibility.Visible; CancelUploadButton.IsEnabled = true;
        UploadProgress.Visibility = Visibility.Visible; UploadProgress.IsIndeterminate = true;
        SetBusy(true, "Checking repository and queued files…");
        try
        {
            var metadata = await _repositoryService.GetRepositoryAsync(identity[0], identity[1], _token, cancellation.Token);
            if (metadata.Archived || metadata.Disabled) throw new InvalidOperationException("This repository is archived or disabled.");
            if (metadata.CanPush == false) throw new InvalidOperationException("GitHub confirms that this account cannot push to this repository.");
            if (metadata.CanPush is null && MessageBox.Show(this, "GitHub did not report write permission for this repository. Continue with branch and file checks?", "Write access could not be confirmed", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
            using (var branchResponse = await SendAsync(HttpMethod.Get, $"https://api.github.com/repos/{repository}/branches/{Uri.EscapeDataString(branch)}", _token, cancellationToken: cancellation.Token)) await EnsureSuccess(branchResponse);

            var existingPaths = new List<string>();
            _queueExistingShas.Clear();
            foreach (var item in items)
            {
                cancellation.Token.ThrowIfCancellationRequested();
                var target = await _repositoryService.GetTargetFileAsync(identity[0], identity[1], branch, item.DestinationPath, _token, cancellation.Token);
                if (target.Exists) { existingPaths.Add(item.DestinationPath); _queueExistingShas[item.DestinationPath] = target.Sha; }
            }
            var policy = UploadCollisionPolicy.Skip;
            if (existingPaths.Count > 0)
            {
                var choice = MessageBox.Show(this, $"{existingPaths.Count} destination file(s) already exist. Choose Yes to replace them, No to skip collisions, or Cancel to stop.\n\n{string.Join("\n", existingPaths.Take(8))}{(existingPaths.Count > 8 ? "\n…" : "")}", "Resolve upload collisions", MessageBoxButton.YesNoCancel, MessageBoxImage.Warning);
                if (choice == MessageBoxResult.Cancel) return;
                policy = choice == MessageBoxResult.Yes ? UploadCollisionPolicy.Replace : UploadCollisionPolicy.Skip;
            }
            _uploadQueue = new UploadQueueService(UploadQueuePlanner.ApplyCollisionPolicy(items, existingPaths, policy));
            _uploadQueue.Changed += (_, _) => Dispatcher.BeginInvoke(new Action(RefreshQueueView));
            var total = _uploadQueue.Items.Count(item => item.State != UploadQueueItemState.Skipped);
            if (total == 0) { SetStatus("Every queued destination already exists and was set to skip. Nothing was uploaded."); return; }
            var destinations = string.Join("\n", _uploadQueue.Items.Where(item => item.State != UploadQueueItemState.Skipped).Take(8).Select(item => item.DestinationPath));
            if (total > 8) destinations += "\n…";
            var confirm = MessageBox.Show(this, $"Upload {total} file(s) to {repository} on {branch}?\n\nAccount: {_account}\nDestination paths:\n{destinations}\nCommit message: {message}\nEach file creates a separate GitHub commit.", "Review folder batch", MessageBoxButton.YesNo, MessageBoxImage.Question);
            if (confirm != MessageBoxResult.Yes) return;
            UploadProgress.IsIndeterminate = false;
            await _uploadQueue.RunAsync(async (item, itemProgress, ct) =>
            {
                var targetPath = item.DestinationPath;
                if (LooksSensitive(Path.GetFileName(item.SourcePath)) && Dispatcher.Invoke(() => MessageBox.Show(this,
                    $"{Path.GetFileName(item.SourcePath)} may contain credentials or private keys. It can remain in repository history after deletion. Upload this file?",
                    "Possible secret file", MessageBoxButton.YesNo, MessageBoxImage.Warning)) != MessageBoxResult.Yes)
                    throw new OperationCanceledException("User declined a potentially sensitive file.", ct);
                if (item.CapturedLength > MaxUploadBytes) throw new InvalidOperationException("This file exceeds the 50 MB per-file limit.");
                var bytes = await ReadStableFileAsync(item.SourcePath, item.CapturedLength, item.CapturedLastWriteTimeUtc, ct);
                await ValidateUploadContentAsync(item.SourcePath, bytes, ct);
                if (bytes.LongLength > MaxUploadBytes) throw new InvalidOperationException("The file grew larger than 50 MB after queueing.");
                var encoded = string.Join("/", targetPath.Split('/').Select(Uri.EscapeDataString));
                using var content = new UploadJsonContent(bytes, message, branch, _queueExistingShas.GetValueOrDefault(targetPath), new Progress<double>(value =>
                {
                    itemProgress.Report(value * 100);
                    Dispatcher.BeginInvoke(new Action(() => UploadProgress.Value = value * 100));
                }));
                using var response = await SendAsync(HttpMethod.Put, $"https://api.github.com/repos/{repository}/contents/{encoded}", _token, content, ct);
                await EnsureSuccess(response);
            }, cancellation.Token);
            var succeeded = _uploadQueue.Items.Count(item => item.State == UploadQueueItemState.Succeeded);
            var failed = _uploadQueue.Items.Count(item => item.State == UploadQueueItemState.Failed);
            QueueStatusLabel.Text = $"Batch finished · {succeeded} uploaded · {failed} failed · {_uploadQueue.Items.Count(item => item.State == UploadQueueItemState.Skipped)} skipped.";
            SetStatus(QueueStatusLabel.Text);
            var preset = $"{repository}|{branch}|{QueuePathBox.Text.Trim()}";
            _destinationHistory.Remove(preset); _destinationHistory.Insert(0, preset);
            if (_destinationHistory.Count > 12) _destinationHistory.RemoveAt(_destinationHistory.Count - 1);
            DestinationPicker.ItemsSource = null; DestinationPicker.ItemsSource = _destinationHistory; SaveSettings();
        }
        catch (OperationCanceledException) { SetStatus("Folder batch canceled. Check GitHub before retrying; the last commit may have completed.", true); }
        catch (Exception ex) { SetStatus(SafeMessage(ex), true); }
        finally
        {
            _uploadCancellation?.Dispose(); _uploadCancellation = null;
            CancelUploadButton.Visibility = Visibility.Collapsed; CancelUploadButton.IsEnabled = false;
            UploadProgress.Visibility = Visibility.Collapsed; UploadProgress.IsIndeterminate = false; UploadProgress.Value = 0;
            SetBusy(false); RefreshQueueView();
        }
    }

    private async void QueueRunWindow_Click(object sender, RoutedEventArgs e)
        => await OpenBatchWindowAsync(false);

    private async void ResumeBatch_Click(object sender, RoutedEventArgs e)
        => await OpenBatchWindowAsync(true);

    private async Task OpenBatchWindowAsync(bool restoreOnly)
    {
        if ((!restoreOnly && _uploadQueue is null) || string.IsNullOrWhiteSpace(_token) || string.IsNullOrWhiteSpace(_account)) { SetStatus("Connect a GitHub account and choose a folder first.", true); return; }
        if (restoreOnly && _appPreferences.PrivacyMode) { SetStatus("Saved queue recovery is disabled in privacy mode.", true); return; }
        var repository = RepoPicker.Text.Trim(); var branch = BranchBox.Text.Trim(); var message = CommitMessageBox.Text.Trim();
        var folder = QueuePathBox.Text.Trim().Replace('\\', '/').Trim('/');
        if (!restoreOnly && !string.Equals(folder, _queuedDestinationFolder, StringComparison.Ordinal)) { SetStatus("The destination folder changed after queueing. Choose the local folder again to rebuild it.", true); return; }
        if (!RepositoryPattern.IsMatch(repository) || branch.Length == 0 || message.Length is < 1 or > 250) { SetStatus("Check the repository, branch, and commit message.", true); return; }
        var sourceItems = restoreOnly ? Array.Empty<UploadQueueItem>() : _uploadQueue!.Items.Where(x => x.State is UploadQueueItemState.Queued or UploadQueueItemState.Failed).ToArray();
        if (!restoreOnly && sourceItems.Length == 0) return;
        using var cts = new CancellationTokenSource();
        _uploadCancellation = cts; CancelUploadButton.Visibility = Visibility.Visible; CancelUploadButton.IsEnabled = true;
        SetBusy(true, "Checking repository and destination conflicts…");
        var shas = new Dictionary<string, string?>(StringComparer.Ordinal);
        try
        {
            var parts = repository.Split('/', 2);
            var metadata = await _repositoryService.GetRepositoryAsync(parts[0], parts[1], _token, cts.Token);
            if (metadata.Archived || metadata.Disabled || metadata.CanPush == false) throw new InvalidOperationException("The repository is archived, disabled, or not writable.");
            if (metadata.CanPush is null && MessageBox.Show(this, "GitHub did not confirm write access. Continue with destination checks?", "Write access unconfirmed", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
            using (var branchResponse = await SendAsync(HttpMethod.Get, $"https://api.github.com/repos/{repository}/branches/{Uri.EscapeDataString(branch)}", _token, cancellationToken: cts.Token)) await EnsureSuccess(branchResponse);
            var existing = new List<string>();
            foreach (var item in sourceItems)
            {
                cts.Token.ThrowIfCancellationRequested();
                var target = await _repositoryService.GetTargetFileAsync(parts[0], parts[1], branch, item.DestinationPath, _token, cts.Token);
                if (target.Exists) { existing.Add(item.DestinationPath); shas[item.DestinationPath] = target.Sha; }
            }
            var policy = UploadCollisionPolicy.Skip;
            if (existing.Count > 0)
            {
                var choice = MessageBox.Show(this, $"{existing.Count} path(s) already exist. Yes replaces them; No renames colliding files; Cancel stops.\n\n{string.Join("\n", existing.Take(6))}", "Resolve GitHub conflicts", MessageBoxButton.YesNoCancel, MessageBoxImage.Warning);
                if (choice == MessageBoxResult.Cancel) return;
                policy = choice == MessageBoxResult.Yes ? UploadCollisionPolicy.Replace : UploadCollisionPolicy.Rename;
            }
            var planned = UploadQueuePlanner.ApplyCollisionPolicy(sourceItems, existing, policy);
            var transferNotice = GetNetworkNotice();
            LogTransfer($"Starting {planned.Count} file(s) to {repository}/{folder} via {DetectNetwork().Name}. {transferNotice}");
            var dialog = new BatchUploadWindow(planned, repository, branch, message, async (file, progress, ct) =>
            {
                if (new FileSafetyRules(_sensitivePatterns.Length == 0 ? null : _sensitivePatterns).Match(file.SourcePath).Count > 0 &&
                    Dispatcher.Invoke(() => MessageBox.Show(this, $"{Path.GetFileName(file.SourcePath)} matches a sensitive-file rule. It may contain credentials and remain in Git history. Upload it?", "Sensitive file warning", MessageBoxButton.YesNo, MessageBoxImage.Warning)) != MessageBoxResult.Yes)
                    throw new OperationCanceledException("Upload declined for a sensitive file.", ct);
                if (file.Size > MaxUploadBytes) throw new InvalidOperationException("This file exceeds the 50 MiB limit.");
                if (file.CapturedLastWriteTimeUtc is not DateTime captured) throw new InvalidOperationException("Review the source file again before uploading.");
                var bytes = await ReadStableFileAsync(file.SourcePath, file.Size, captured, ct);
                await ValidateUploadContentAsync(file.SourcePath, bytes, ct);
                var encodedPath = string.Join("/", file.DestinationPath.Split('/').Select(Uri.EscapeDataString));
                var target = await _repositoryService.GetTargetFileAsync(parts[0], parts[1], branch, file.DestinationPath, _token!, ct);
                if (target.Exists && MessageBox.Show(this, $"Replace the current GitHub file at {file.DestinationPath}?", "Review destination", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
                    throw new OperationCanceledException("Destination replacement declined.", ct);
                var destinationSha = target.Sha;
                LogTransfer($"Uploading {Path.GetFileName(file.SourcePath)} to {repository}/{file.DestinationPath} · {FormatSize(bytes.Length)}.");
                using var content = new UploadJsonContent(bytes, file.CommitMessage, branch, destinationSha,
                    new Progress<double>(value => progress.Report(value * 100)));
                using var response = await SendAsync(HttpMethod.Put, $"https://api.github.com/repos/{repository}/contents/{encodedPath}", _token!, content, ct);
                try { await EnsureSuccess(response); }
                catch (Exception ex) { LogTransfer($"Upload failed: {repository}/{file.DestinationPath}: {SafeMessage(ex)}"); throw; }
                string? htmlUrl = null;
                try { using var json = JsonDocument.Parse(await response.Content.ReadAsStringAsync()); htmlUrl = json.RootElement.GetProperty("content").GetProperty("html_url").GetString(); } catch { }
                LogTransfer($"Upload complete: {repository}/{file.DestinationPath}.");
                return new BatchUploadResult(file.SourcePath, true, htmlUrl);
            }, uploadBatch: async (files, batchMessage, progress, ct) =>
            {
                var service = new GitHubAtomicBatchService(_http);
                var expectedHead = await service.GetHeadAsync(parts[0], parts[1], branch, _token!, ct);
                var replacements = new List<string>();
                foreach (var file in files)
                {
                    ct.ThrowIfCancellationRequested();
                    if ((LooksSensitive(file.SourcePath) || LooksSensitive(file.DestinationPath)) && MessageBox.Show(this,
                        $"{Path.GetFileName(file.SourcePath)} matches a sensitive-file rule. Include it in this commit?", "Sensitive file warning", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
                        throw new OperationCanceledException("Sensitive file declined.", ct);
                    var target = await _repositoryService.GetTargetFileAsync(parts[0], parts[1], branch, file.DestinationPath, _token!, ct);
                    if (target.Exists) replacements.Add(file.DestinationPath);
                }
                if (replacements.Count > 0 && MessageBox.Show(this,
                    $"This commit replaces {replacements.Count} current file(s):\n\n{string.Join("\n", replacements.Take(12))}\n\nContinue?",
                    "Review batch replacements", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
                    throw new OperationCanceledException("Batch replacement declined.", ct);
                return await service.UploadAsync(parts[0], parts[1], branch, _token!, files, batchMessage,
                    expectedHead, progress, ct, ValidateUploadContentAsync);
            }, transferNotice: transferNotice, persistQueue: !_appPreferences.PrivacyMode) { Owner = this };
            _ = dialog.ShowDialog();
            if (dialog.FinalResults is { } results)
            {
                var ok = results.Count(x => x.Succeeded); var failed = results.Count(x => !x.Succeeded);
                QueueStatusLabel.Text = $"Batch complete · {ok} uploaded · {failed} failed or skipped.";
                SetStatus(QueueStatusLabel.Text);
                LogTransfer($"Batch complete for {repository}: {ok} uploaded, {failed} failed or skipped.");
                if (!_appPreferences.PrivacyMode)
                    _appPreferences = _appPreferences with { RecentRepositories = new[] { repository }.Concat(_appPreferences.RecentRepositories).Distinct(StringComparer.OrdinalIgnoreCase).Take(20).ToArray() };
                if (folder.Length > 0)
                {
                    var defaults = new Dictionary<string, string>(_appPreferences.DefaultUploadFolders, StringComparer.OrdinalIgnoreCase) { [repository] = folder };
                    _appPreferences = _appPreferences with { DefaultUploadFolders = defaults };
                }
                SaveSettings();
            }
        }
        catch (OperationCanceledException) { SetStatus("Batch check or upload canceled. Check GitHub before retrying; a request may have completed.", true); }
        catch (Exception ex) { SetStatus(SafeMessage(ex), true); }
        finally { _uploadCancellation = null; CancelUploadButton.Visibility = Visibility.Collapsed; CancelUploadButton.IsEnabled = false; SetBusy(false); RefreshQueueView(); }
    }

    private void QueuePause_Click(object sender, RoutedEventArgs e)
    {
        if (_uploadQueue?.IsPaused == true) _uploadQueue.Resume(); else _uploadQueue?.Pause();
        RefreshQueueView();
    }

    private void QueueRetry_Click(object sender, RoutedEventArgs e)
    {
        try { _uploadQueue?.RetryFailed(); QueueStatusLabel.Text = "Failed items returned to the queue."; }
        catch (Exception ex) { SetStatus(ex.Message, true); }
        RefreshQueueView();
    }

    private static bool IsSafePath(string value) => value.Length is > 0 and <= 400
        && !value.StartsWith('/') && !value.EndsWith('/')
        && value.Split('/').All(part => part.Length > 0 && part != "." && part != ".." && !part.Any(char.IsControl));

    private static async Task<byte[]> ReadStableFileAsync(string path, long expectedLength, DateTime expectedLastWriteTimeUtc, CancellationToken cancellationToken)
    {
        await using var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read,
            128 * 1024, FileOptions.Asynchronous | FileOptions.SequentialScan);
        if (input.Length != expectedLength || File.GetLastWriteTimeUtc(path) != expectedLastWriteTimeUtc)
            throw new InvalidOperationException("The file changed after it was queued or reviewed. Search or queue it again before uploading.");
        if (input.Length > MaxUploadBytes) throw new InvalidOperationException("Files larger than 50 MB cannot be uploaded.");
        using var output = new MemoryStream(checked((int)input.Length));
        await input.CopyToAsync(output, 128 * 1024, cancellationToken);
        if (output.Length != expectedLength) throw new InvalidOperationException("The file could not be read completely. Nothing was uploaded.");
        return output.ToArray();
    }

    private bool LooksSensitive(string name) =>
        new FileSafetyRules(_sensitivePatterns.Length == 0 ? null : _sensitivePatterns).Match(name).Count > 0;

    private async Task<(string Token, string Username)> GetCredentialAsync(string account)
    {
        var start = new ProcessStartInfo("git", "credential fill")
        {
            UseShellExecute = false, RedirectStandardInput = true, RedirectStandardOutput = true,
            RedirectStandardError = true, CreateNoWindow = true
        };
        start.Environment["GCM_INTERACTIVE"] = "never";
        start.Environment["GIT_TERMINAL_PROMPT"] = "0";
        using var process = new Process { StartInfo = start };
        try { if (!process.Start()) throw new InvalidOperationException(); }
        catch { throw new InvalidOperationException("Git Credential Manager could not start. Install Git for Windows and sign in to GitHub."); }
        await process.StandardInput.WriteAsync($"protocol=https\nhost=github.com\nusername={account}\n\n");
        process.StandardInput.Close();
        var outputTask = process.StandardOutput.ReadToEndAsync();
        await process.WaitForExitAsync();
        var output = await outputTask;
        if (process.ExitCode != 0) throw new InvalidOperationException("No saved GitHub login was found. Sign in to GitHub with Git for Windows Credential Manager, then press Connect again.");
        var fields = output.Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(line => line.Trim().Split('=', 2)).Where(pair => pair.Length == 2).ToDictionary(pair => pair[0], pair => pair[1]);
        if (!fields.TryGetValue("password", out var token) || string.IsNullOrWhiteSpace(token) || !fields.TryGetValue("username", out var username))
            throw new InvalidOperationException("The saved GitHub login is incomplete. Refresh it with Git Credential Manager, then connect again.");
        return (token, username);
    }

    private async Task<HttpResponseMessage> SendAsync(HttpMethod method, string url, string token, HttpContent? content = null, CancellationToken cancellationToken = default)
    {
        using var request = new HttpRequestMessage(method, url) { Content = content };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.4");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        return await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken);
    }

    private static async Task EnsureSuccess(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode) return;
        var detail = string.Empty;
        try
        {
            var body = await response.Content.ReadAsStringAsync();
            using var error = JsonDocument.Parse(body);
            if (error.RootElement.TryGetProperty("message", out var message) && message.ValueKind == JsonValueKind.String)
                detail = message.GetString() ?? string.Empty;
        }
        catch { /* Keep the useful status-based explanation when GitHub returns no JSON body. */ }
        if (detail.Length > 400) detail = detail[..400] + "…";

        var reason = response.StatusCode switch
        {
            HttpStatusCode.Unauthorized => "GitHub rejected the saved login. Sign in again with Git Credential Manager.",
            HttpStatusCode.Forbidden when response.Headers.TryGetValues("X-RateLimit-Remaining", out var remaining) && remaining.FirstOrDefault() == "0"
                => "GitHub API rate limit reached. Wait for the reset time and retry.",
            HttpStatusCode.Forbidden => "GitHub denied this action. Check repository write access and organization approval.",
            HttpStatusCode.NotFound => "GitHub could not find that repository, branch, or file, or the account cannot access it.",
            (HttpStatusCode)422 => "GitHub rejected this commit. Check branch protection, path, or repository rules.",
            HttpStatusCode.Conflict => "The repository changed during upload. Refresh the destination and try again.",
            _ => $"GitHub returned HTTP {(int)response.StatusCode}. Check your connection and try again."
        };
        throw new InvalidOperationException(string.IsNullOrWhiteSpace(detail) ? reason : $"{reason} GitHub: {detail}");
    }

    private static string SafeMessage(Exception ex) => ex is HttpRequestException or TaskCanceledException
        ? "Could not reach GitHub. Check your internet connection and try again."
        : ex.Message;
    private static string FormatSize(long bytes) => bytes < 1024 * 1024 ? $"{bytes / 1024d:0.#} KB" : $"{bytes / (1024d * 1024):0.##} MB";
    private void SetStatus(string message, bool error = false)
    {
        StatusLabel.Text = message;
        StatusLabel.Foreground = new SolidColorBrush(error ? Color.FromRgb(255, 137, 155) : Color.FromRgb(192, 203, 224));
    }
    private void SetBusy(bool busy, string? message = null)
    {
        _busy = busy; SearchButton.IsEnabled = !busy; QueueFolderButton.IsEnabled = !busy; QueuePathBox.IsEnabled = !busy; QueueRunButton.IsEnabled = !busy && _uploadQueue is not null && _token is not null; ConnectButton.IsEnabled = !busy;
        AccountPicker.IsEnabled = !busy; AddAccountButton.IsEnabled = !busy; SignOutButton.IsEnabled = !busy && _account is not null;
        BrowseButton.IsEnabled = !busy;
        UploadButton.IsEnabled = !busy && ResultsList.SelectedItem is ResultItem && _token is not null;
        if (message is not null) SetStatus(message);
        Mouse.OverrideCursor = busy ? Cursors.Wait : null;
    }

    private sealed class UploadJsonContent : HttpContent
    {
        private readonly byte[] _file;
        private readonly byte[] _prefix;
        private readonly byte[] _suffix;
        private readonly IProgress<double> _progress;
        private const int ChunkSize = 196608; // divisible by 3, so base64 chunks concatenate cleanly

        public UploadJsonContent(byte[] file, string message, string branch, string? sha, IProgress<double> progress)
        {
            _file = file;
            _progress = progress;
            _prefix = Encoding.UTF8.GetBytes("{\"message\":" + JsonSerializer.Serialize(message) + ",\"content\":\"");
            _suffix = Encoding.UTF8.GetBytes("\",\"branch\":" + JsonSerializer.Serialize(branch)
                + (sha is null ? string.Empty : ",\"sha\":" + JsonSerializer.Serialize(sha)) + "}");
            Headers.ContentType = new MediaTypeHeaderValue("application/json") { CharSet = "utf-8" };
        }

        protected override bool TryComputeLength(out long length)
        {
            length = _prefix.LongLength + ((_file.LongLength + 2) / 3 * 4) + _suffix.LongLength;
            return true;
        }

        protected override Task SerializeToStreamAsync(Stream stream, TransportContext? context) =>
            SerializeToStreamAsync(stream, context, CancellationToken.None);

        protected override async Task SerializeToStreamAsync(Stream stream, TransportContext? context, CancellationToken cancellationToken)
        {
            await stream.WriteAsync(_prefix, 0, _prefix.Length, cancellationToken);
            var offset = 0;
            while (offset < _file.Length)
            {
                cancellationToken.ThrowIfCancellationRequested();
                var count = Math.Min(ChunkSize, _file.Length - offset);
                var base64 = Encoding.ASCII.GetBytes(Convert.ToBase64String(_file, offset, count));
                await stream.WriteAsync(base64, 0, base64.Length, cancellationToken);
                offset += count;
                _progress.Report(_file.Length == 0 ? 1 : (double)offset / _file.Length);
            }
            if (_file.Length == 0) _progress.Report(1);
            await stream.WriteAsync(_suffix, 0, _suffix.Length, cancellationToken);
        }
    }

    private sealed class ResultItem
    {
        public string FullPath { get; }
        public string Name => Path.GetFileName(FullPath);
        public long Size { get; }
        public DateTime LastModified { get; }
        public DateTime LastWriteTimeUtc { get; }
        public ResultItem(string path, long size, DateTime lastModified, DateTime lastWriteTimeUtc)
        {
            FullPath = path; Size = size; LastModified = lastModified;
            LastWriteTimeUtc = lastWriteTimeUtc;
        }
        public bool HasChangedOnDisk() => !File.Exists(FullPath) || new FileInfo(FullPath).Length != Size || File.GetLastWriteTimeUtc(FullPath) != LastWriteTimeUtc;
        public string Details => $"{Name}   ·   {FormatSize(Size)}   ·   {LastModified:yyyy-MM-dd HH:mm}\n{FullPath}";
        public string Summary => $"{FormatSize(Size)}  ·  {LastModified:yyyy-MM-dd HH:mm}";
    }

    private enum SearchSort { Name, Largest, Newest, Oldest }
    private sealed record SearchConfiguration(global::FileToGitHub.SearchOptions Options, SearchSort SortBy);

    private sealed record RepoChoice(string FullName, string DefaultBranch)
    {
        public override string ToString() => FullName;
    }

    private sealed record GitHubProjectChoice(string FullName, string Description, string DefaultBranch, bool IsPrivate, string? UpdatedAt, string? HtmlUrl)
    {
        public string VisibilityLabel => IsPrivate ? "PRIVATE" : "PUBLIC";
        public string Details
        {
            get
            {
                var updated = DateTimeOffset.TryParse(UpdatedAt, out var date) ? date.ToLocalTime().ToString("yyyy-MM-dd") : "date unavailable";
                return $"Default branch: {DefaultBranch}   ·   Updated: {updated}";
            }
        }
    }
}
