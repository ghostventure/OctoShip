using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

/// <summary>Read-only GitHub REST operations used to inspect upload destinations.</summary>
public sealed class GitHubRepositoryService
{
    private const string ApiRoot = "https://api.github.com";
    private static readonly Regex NamePattern = new("^[A-Za-z0-9_.-]+$", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private readonly HttpClient _http;

    /// <summary>The caller owns and configures the HTTP client lifetime.</summary>
    public GitHubRepositoryService(HttpClient httpClient)
    {
        _http = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
    }

    public async Task<RepositoryMetadata> GetRepositoryAsync(string owner, string repository, string token, CancellationToken cancellationToken = default)
    {
        ValidateIdentity(owner, repository, token);
        using var response = await SendAsync($"/repos/{Segment(owner)}/{Segment(repository)}", token, cancellationToken).ConfigureAwait(false);
        await EnsureSuccessAsync(response, cancellationToken).ConfigureAwait(false);
        using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false), cancellationToken: cancellationToken).ConfigureAwait(false);
        var root = doc.RootElement;
        return new RepositoryMetadata(
            GetString(root, "full_name") ?? $"{owner}/{repository}",
            GetString(root, "visibility") ?? (GetBool(root, "private") ? "private" : "public"),
            GetBool(root, "private"), GetBool(root, "archived"), GetBool(root, "disabled"),
            GetString(root, "default_branch"), ReadPushPermission(root));
    }

    public async Task<IReadOnlyList<BranchInfo>> ListBranchesAsync(string owner, string repository, string token, CancellationToken cancellationToken = default)
    {
        ValidateIdentity(owner, repository, token);
        var branches = new List<BranchInfo>();
        for (var page = 1; page <= 10; page++)
        {
            using var response = await SendAsync($"/repos/{Segment(owner)}/{Segment(repository)}/branches?per_page=100&page={page}", token, cancellationToken).ConfigureAwait(false);
            await EnsureSuccessAsync(response, cancellationToken).ConfigureAwait(false);
            using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false), cancellationToken: cancellationToken).ConfigureAwait(false);
            var batch = doc.RootElement.EnumerateArray().Select(item => new BranchInfo(
                GetString(item, "name") ?? string.Empty,
                item.TryGetProperty("commit", out var commit) ? GetString(commit, "sha") : null,
                GetBool(item, "protected"))).ToArray();
            branches.AddRange(batch);
            if (batch.Length < 100) return branches;
        }
        return branches;
    }

    public async Task<TargetFileInfo> GetTargetFileAsync(string owner, string repository, string branch, string path, string token, CancellationToken cancellationToken = default)
    {
        ValidateIdentity(owner, repository, token);
        ValidateBranch(branch);
        ValidatePath(path);
        var url = $"/repos/{Segment(owner)}/{Segment(repository)}/contents/{PathSegments(path)}?ref={Uri.EscapeDataString(branch)}";
        using var response = await SendAsync(url, token, cancellationToken).ConfigureAwait(false);
        if (response.StatusCode == HttpStatusCode.NotFound) return new TargetFileInfo(false, null, null, null);
        await EnsureSuccessAsync(response, cancellationToken).ConfigureAwait(false);
        using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false), cancellationToken: cancellationToken).ConfigureAwait(false);
        var root = doc.RootElement;
        if (!string.Equals(GetString(root, "type"), "file", StringComparison.Ordinal))
            throw new InvalidOperationException("The selected GitHub path exists but is not a file.");
        return new TargetFileInfo(true, GetString(root, "sha"), GetString(root, "html_url"), GetLong(root, "size"));
    }

    public async Task<RateLimitInfo> GetRateLimitAsync(string token, CancellationToken cancellationToken = default)
    {
        ValidateToken(token);
        using var response = await SendAsync("/rate_limit", token, cancellationToken).ConfigureAwait(false);
        await EnsureSuccessAsync(response, cancellationToken).ConfigureAwait(false);
        using var doc = await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false), cancellationToken: cancellationToken).ConfigureAwait(false);
        var resources = doc.RootElement.GetProperty("resources");
        var core = resources.GetProperty("core");
        var search = resources.TryGetProperty("search", out var searchElement) ? ReadRate(searchElement) : null;
        return new RateLimitInfo(ReadRate(core), search);
    }

    /// <summary>Combines repository state, write permission and target path existence without changing remote data.</summary>
    public async Task<UploadPreflight> CheckUploadPreflightAsync(string owner, string repository, string branch, string path, string token, CancellationToken cancellationToken = default)
    {
        ValidateIdentity(owner, repository, token);
        ValidateBranch(branch);
        ValidatePath(path);
        var metadata = await GetRepositoryAsync(owner, repository, token, cancellationToken).ConfigureAwait(false);
        if (metadata.Archived || metadata.Disabled)
            return new UploadPreflight(metadata, false, false, null, "Repository is archived or disabled.");
        if (metadata.CanPush != true)
            return new UploadPreflight(metadata, false, false, null, metadata.CanPush == false ? "The authenticated account does not have repository push permission." : "GitHub did not provide push permission details; access could not be confirmed.");
        try
        {
            var target = await GetTargetFileAsync(owner, repository, branch, path, token, cancellationToken).ConfigureAwait(false);
            return new UploadPreflight(metadata, true, true, target, target.Exists ? "Ready; this path already contains a file." : "Ready; this path is available.");
        }
        catch (HttpRequestException ex) when (ex.StatusCode == HttpStatusCode.NotFound)
        {
            return new UploadPreflight(metadata, true, false, null, "Repository is writable, but the branch or target path could not be found.");
        }
    }

    private async Task<HttpResponseMessage> SendAsync(string relativePath, string token, CancellationToken cancellationToken)
    {
        ValidateToken(token);
        using var request = new HttpRequestMessage(HttpMethod.Get, ApiRoot + relativePath);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.4");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        return await _http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
    }

    private static Task EnsureSuccessAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode) return Task.CompletedTask;
        var status = response.StatusCode;
        var reason = status switch
        {
            HttpStatusCode.Unauthorized => "GitHub rejected the supplied credential.",
            HttpStatusCode.Forbidden => "GitHub denied this read request; access or API rate limits may apply.",
            HttpStatusCode.NotFound => "GitHub could not find the repository, branch, or path, or the account cannot access it.",
            _ => $"GitHub returned HTTP {(int)status} ({status})."
        };
        throw new HttpRequestException(reason, null, status);
    }

    private static void ValidateIdentity(string owner, string repository, string token)
    {
        if (string.IsNullOrWhiteSpace(owner) || !NamePattern.IsMatch(owner) || owner is "." or "..") throw new ArgumentException("Invalid GitHub owner name.", nameof(owner));
        if (string.IsNullOrWhiteSpace(repository) || !NamePattern.IsMatch(repository) || repository is "." or "..") throw new ArgumentException("Invalid GitHub repository name.", nameof(repository));
        ValidateToken(token);
    }

    private static void ValidateToken(string token)
    {
        if (string.IsNullOrWhiteSpace(token) || token.Any(char.IsControl)) throw new ArgumentException("A valid GitHub token must be supplied in memory.", nameof(token));
    }

    private static void ValidateBranch(string branch)
    {
        if (string.IsNullOrWhiteSpace(branch) || branch.Length > 255 || branch[0] == '/' || branch[^1] == '/' || branch.Contains("..", StringComparison.Ordinal) || branch.Contains("//", StringComparison.Ordinal) || branch.Contains("@{", StringComparison.Ordinal) || branch.Any(c => char.IsControl(c) || c is ' ' or '~' or '^' or ':' or '?' or '*' or '[' or '\\'))
            throw new ArgumentException("Invalid Git branch name.", nameof(branch));
    }

    private static void ValidatePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path) || path.Length > 1024 || path.StartsWith('/') || path.Contains('\\') || path.Any(char.IsControl)) throw new ArgumentException("Invalid repository file path.", nameof(path));
        if (path.Split('/').Any(segment => segment.Length == 0 || segment is "." or "..")) throw new ArgumentException("Repository path must contain safe, non-empty path segments.", nameof(path));
    }

    private static string Segment(string value) => Uri.EscapeDataString(value);
    private static string PathSegments(string path) => string.Join("/", path.Split('/').Select(Uri.EscapeDataString));
    private static string? GetString(JsonElement element, string property) => element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
    private static bool GetBool(JsonElement element, string property) => element.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.True;
    private static long? GetLong(JsonElement element, string property) => element.TryGetProperty(property, out var value) && value.TryGetInt64(out var number) ? number : null;
    private static bool? ReadPushPermission(JsonElement root) => root.TryGetProperty("permissions", out var permissions) && permissions.TryGetProperty("push", out var push) && push.ValueKind is JsonValueKind.True or JsonValueKind.False ? push.GetBoolean() : null;
    private static RateLimitBucket ReadRate(JsonElement element) => new(GetLong(element, "limit") ?? 0, GetLong(element, "remaining") ?? 0, DateTimeOffset.FromUnixTimeSeconds(GetLong(element, "reset") ?? 0));

    public sealed record RepositoryMetadata(string FullName, string Visibility, bool IsPrivate, bool Archived, bool Disabled, string? DefaultBranch, bool? CanPush);
    public sealed record BranchInfo(string Name, string? CommitSha, bool Protected);
    public sealed record TargetFileInfo(bool Exists, string? Sha, string? HtmlUrl, long? Size);
    public sealed record RateLimitBucket(long Limit, long Remaining, DateTimeOffset ResetsAt);
    public sealed record RateLimitInfo(RateLimitBucket Core, RateLimitBucket? Search);
    public sealed record UploadPreflight(RepositoryMetadata Repository, bool WriteAccessConfirmed, bool TargetLookupSucceeded, TargetFileInfo? Target, string Message);
}
