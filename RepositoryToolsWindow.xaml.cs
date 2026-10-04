using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace FileToGitHub;

/// <summary>Read-only GitHub repository folder browser. Credentials are requested from the caller only when needed and never retained.</summary>
public partial class RepositoryToolsWindow : Window
{
    private static readonly Regex RepositoryPattern = new("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private readonly HttpClient _http;
    private readonly Func<string?> _tokenProvider;
    private readonly IReadOnlyList<string> _recentRepositories;
    private readonly CancellationTokenSource _lifetime = new();
    private string _folder = "";
    private bool _loading;

    public string? SelectedRepository { get; private set; }
    public string? SelectedBranch { get; private set; }
    public string? SelectedFolder { get; private set; }

    public RepositoryToolsWindow(HttpClient httpClient, Func<string?> tokenProvider, IEnumerable<string>? recentRepositories = null,
        string? repository = null, string? branch = null, string? defaultFolder = null)
    {
        InitializeComponent();
        _http = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _tokenProvider = tokenProvider ?? throw new ArgumentNullException(nameof(tokenProvider));
        _recentRepositories = (recentRepositories ?? Array.Empty<string>()).Where(IsRepository).Distinct(StringComparer.OrdinalIgnoreCase).Take(30).ToArray();
        RecentList.ItemsSource = _recentRepositories;
        RepositoryBox.Text = repository ?? "";
        BranchInput.Text = string.IsNullOrWhiteSpace(branch) ? "main" : branch;
        _folder = defaultFolder?.Trim('/') ?? "";
        PathInput.Text = _folder;
        Closed += (_, _) => _lifetime.Cancel();
    }

    private async void LoadRepository_Click(object sender, RoutedEventArgs e) => await LoadFolderAsync("");
    private async void Refresh_Click(object sender, RoutedEventArgs e) => await LoadFolderAsync(_folder);
    private void Cancel_Click(object sender, RoutedEventArgs e) => Close();

    private void Workflow_Click(object sender, RoutedEventArgs e)
    {
        new RepositoryWorkflowWindow(_http, _tokenProvider, RepositoryBox.Text.Trim(), BranchInput.Text.Trim(), PathInput.Text.Trim()) { Owner = this }.ShowDialog();
    }

    private async void CheckConnection_Click(object sender, RoutedEventArgs e)
    {
        if (!TryGetToken(out var token)) return;
        try
        {
            using var request = MakeRequest("https://api.github.com/rate_limit", token);
            using var response = await _http.SendAsync(request, _lifetime.Token);
            response.EnsureSuccessStatusCode();
            using var document = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(_lifetime.Token), cancellationToken: _lifetime.Token);
            var core = document.RootElement.GetProperty("resources").GetProperty("core");
            var remaining = core.GetProperty("remaining").GetInt32();
            var resets = DateTimeOffset.FromUnixTimeSeconds(core.GetProperty("reset").GetInt64()).ToLocalTime();
            SetStatus($"Connected to GitHub. API quota: {remaining} requests remain; reset at {resets:t}.");
        }
        catch (OperationCanceledException) { }
        catch (Exception ex) { SetStatus("GitHub connection check failed: " + SafeApiError(ex), true); }
    }

    private async Task LoadFolderAsync(string folder)
    {
        if (_loading) return;
        var repo = RepositoryBox.Text.Trim();
        var branch = BranchInput.Text.Trim();
        if (!IsRepository(repo)) { SetStatus("Enter a repository as owner/name.", true); return; }
        if (string.IsNullOrWhiteSpace(branch) || branch.Length > 255 || branch.Any(char.IsControl)) { SetStatus("Enter a valid branch name.", true); return; }
        if (!TryGetToken(out var token)) return;
        _loading = true;
        FolderList.ItemsSource = null;
        SetStatus("Loading repository folders…");
        try
        {
            var repoParts = repo.Split('/');
            var encodedPath = string.Join("/", folder.Split('/', StringSplitOptions.RemoveEmptyEntries).Select(Uri.EscapeDataString));
            var url = $"https://api.github.com/repos/{Uri.EscapeDataString(repoParts[0])}/{Uri.EscapeDataString(repoParts[1])}/contents" +
                      (encodedPath.Length == 0 ? "" : "/" + encodedPath) + "?ref=" + Uri.EscapeDataString(branch);
            using var request = MakeRequest(url, token);
            using var response = await _http.SendAsync(request, _lifetime.Token);
            response.EnsureSuccessStatusCode();
            using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(_lifetime.Token), cancellationToken: _lifetime.Token);
            if (doc.RootElement.ValueKind != JsonValueKind.Array) throw new InvalidOperationException("The selected path is not a repository folder.");
            var entries = new List<BrowserEntry>();
            if (folder.Length > 0) entries.Add(new BrowserEntry("..", "Parent folder", ".."));
            foreach (var element in doc.RootElement.EnumerateArray())
            {
                var type = element.TryGetProperty("type", out var typeValue) ? typeValue.GetString() : null;
                if (type is not ("dir" or "file")) continue;
                var name = element.TryGetProperty("name", out var nameValue) ? nameValue.GetString() : null;
                if (string.IsNullOrWhiteSpace(name) || name.Contains('/') || name is "." or "..") continue;
                if (type == "dir") entries.Add(new BrowserEntry(name, "Folder", name));
            }
            _folder = folder;
            PathInput.Text = folder;
            FolderHeading.Text = folder.Length == 0 ? "Repository root" : folder;
            FolderList.ItemsSource = entries;
            SetStatus($"Loaded {entries.Count(entry => entry.Kind == "Folder")} folders. Double-click a folder to open it.");
        }
        catch (OperationCanceledException) { }
        catch (Exception ex) { SetStatus("Could not browse that repository path: " + SafeApiError(ex), true); }
        finally { _loading = false; }
    }

    private async void FolderList_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        if (FolderList.SelectedItem is not BrowserEntry entry || entry.Kind != "Folder") return;
        var next = entry.Name == ".." ? ParentFolder(_folder) : Join(_folder, entry.Name);
        await LoadFolderAsync(next);
    }

    private void Accept_Click(object sender, RoutedEventArgs e)
    {
        var repository = RepositoryBox.Text.Trim();
        var branch = BranchInput.Text.Trim();
        var folder = PathInput.Text.Trim().Trim('/');
        if (!IsRepository(repository)) { SetStatus("Enter a repository as owner/name.", true); return; }
        if (string.IsNullOrWhiteSpace(branch) || branch.Length > 255 || branch.Any(char.IsControl)) { SetStatus("Enter a valid branch name.", true); return; }
        if (!SafeFolder(folder)) { SetStatus("Enter a safe repository folder path.", true); return; }
        SelectedRepository = repository;
        SelectedBranch = branch;
        SelectedFolder = folder;
        DialogResult = true;
        Close();
    }

    private void RecentList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (RecentList.SelectedItem is string repository) RepositoryBox.Text = repository;
    }

    private void FilterBox_TextChanged(object sender, TextChangedEventArgs e)
    {
        if (RecentList is null) return;
        var query = FilterBox.Text.Trim();
        RecentList.ItemsSource = _recentRepositories.Where(repo => repo.Contains(query, StringComparison.OrdinalIgnoreCase)).ToArray();
    }

    private bool TryGetToken(out string token)
    {
        token = _tokenProvider() ?? "";
        if (!string.IsNullOrWhiteSpace(token) && !token.Any(char.IsControl)) return true;
        SetStatus("Sign in to GitHub before browsing repositories.", true);
        return false;
    }

    private static HttpRequestMessage MakeRequest(string url, string token)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.4");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        return request;
    }

    private void SetStatus(string text, bool error = false)
    {
        StatusText.Text = text;
        StatusText.Foreground = error ? System.Windows.Media.Brushes.OrangeRed : System.Windows.Media.Brushes.LightSteelBlue;
    }

    private static bool IsRepository(string value) => RepositoryPattern.IsMatch(value) && value.Split('/').All(part => part is not "." and not "..");
    private static bool SafeFolder(string path) => path.Length <= 1024 && !path.Contains('\\') && !path.Any(char.IsControl) && (path.Length == 0 || path.Split('/').All(part => part.Length > 0 && part is not "." and not ".."));
    private static string Join(string folder, string child) => folder.Length == 0 ? child : folder + "/" + child;
    private static string ParentFolder(string folder) { var slash = folder.LastIndexOf('/'); return slash < 0 ? "" : folder[..slash]; }
    private static string SafeApiError(Exception ex) => ex is HttpRequestException http && http.StatusCode.HasValue ? $"HTTP {(int)http.StatusCode.Value}; check repository access, branch, and API quota." : ex is JsonException ? "GitHub returned an unexpected response." : ex.Message;
    private sealed record BrowserEntry(string Name, string Kind, string Value)
    {
        public override string ToString() => Kind == "Folder" ? "📁  " + Name : Name;
    }
}
