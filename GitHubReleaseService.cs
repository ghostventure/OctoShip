using System;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

public sealed record CreatedRelease(long Id, string HtmlUrl, bool Draft);

/// <summary>Explicit release operations. Creation is always a draft; publishing is a separate call.</summary>
public sealed class GitHubReleaseService
{
    private readonly HttpClient _http;
    public GitHubReleaseService(HttpClient http) => _http = http;

    public async Task<CreatedRelease> CreateDraftAsync(string owner, string repository, string token, string tag, string target, string title, string notes, bool prerelease, CancellationToken ct = default)
    {
        var root = Root(owner, repository);
        if (string.IsNullOrWhiteSpace(tag) || tag.Any(char.IsControl)) throw new ArgumentException("Enter a valid release tag.");
        using var request = Request(HttpMethod.Post, root + "/releases", token);
        request.Content = Json(new { tag_name = tag.Trim(), target_commitish = target, name = title, body = notes, draft = true, prerelease });
        using var response = await _http.SendAsync(request, ct);
        Check(response);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
        return Read(doc.RootElement);
    }

    public async Task UploadAssetAsync(string owner, string repository, string token, long releaseId, string path, CancellationToken ct = default)
    {
        var root = Root(owner, repository).Replace("https://api.github.com/", "https://uploads.github.com/");
        if (releaseId <= 0) throw new ArgumentException("Invalid release ID.");
        await using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true);
        if (file.Length == 0 || file.Length >= 2L * 1024 * 1024 * 1024) throw new ArgumentException("Release assets must be nonempty and smaller than 2 GiB.");
        using var request = Request(HttpMethod.Post, root + $"/releases/{releaseId}/assets?name=" + Uri.EscapeDataString(Path.GetFileName(path)), token);
        request.Content = new StreamContent(file);
        request.Content.Headers.ContentType = new MediaTypeHeaderValue("application/octet-stream");
        request.Content.Headers.ContentLength = file.Length;
        using var response = await _http.SendAsync(request, ct);
        Check(response);
    }

    public async Task<CreatedRelease> PublishAsync(string owner, string repository, string token, long releaseId, CancellationToken ct = default)
    {
        if (releaseId <= 0) throw new ArgumentException("Invalid release ID.");
        using var request = Request(HttpMethod.Patch, Root(owner, repository) + $"/releases/{releaseId}", token);
        request.Content = Json(new { draft = false });
        using var response = await _http.SendAsync(request, ct);
        Check(response);
        using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
        return Read(doc.RootElement);
    }

    private static string Root(string owner, string repo)
    {
        if (new[] { owner, repo }.Any(s => string.IsNullOrWhiteSpace(s) || !Regex.IsMatch(s, "^[A-Za-z0-9_.-]+$") || s is "." or "..")) throw new ArgumentException("Invalid GitHub owner or repository.");
        return $"https://api.github.com/repos/{Uri.EscapeDataString(owner)}/{Uri.EscapeDataString(repo)}";
    }
    private static HttpRequestMessage Request(HttpMethod method, string url, string token)
    {
        if (string.IsNullOrWhiteSpace(token) || token.Any(char.IsControl)) throw new ArgumentException("Supply a GitHub token.");
        var request = new HttpRequestMessage(method, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.5");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        return request;
    }
    private static StringContent Json(object value) => new(JsonSerializer.Serialize(value), Encoding.UTF8, "application/json");
    private static CreatedRelease Read(JsonElement e) => new(e.GetProperty("id").GetInt64(), e.GetProperty("html_url").GetString() ?? "", e.GetProperty("draft").GetBoolean());
    private static void Check(HttpResponseMessage response)
    {
        if (!response.IsSuccessStatusCode) throw new HttpRequestException($"GitHub release operation failed (HTTP {(int)response.StatusCode}). Check repository write permission, tag and asset names. A draft or asset may already exist; inspect GitHub before retrying.", null, response.StatusCode);
    }
}
