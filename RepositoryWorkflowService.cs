using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Explicit branch/PR actions and read-only byte-content comparison.</summary>
public sealed class RepositoryWorkflowService
{
    private readonly HttpClient _http;
    public RepositoryWorkflowService(HttpClient http) => _http = http;
    public sealed record ComparisonRow(string Path, string Status);
    public sealed record ComparisonResult(string Commit, IReadOnlyList<ComparisonRow> Files);

    public async Task<ComparisonResult> CompareAsync(string repository, string branch, string remoteFolder, string localFolder, string token, CancellationToken ct = default)
    {
        ValidateRepository(repository); ValidateBranch(branch);
        remoteFolder = remoteFolder.Trim('/');
        if (remoteFolder.Contains('\\') || remoteFolder.Any(char.IsControl) || (remoteFolder.Length > 0 && remoteFolder.Split('/').Any(x => x.Length == 0 || x is "." or ".."))) throw new ArgumentException("Invalid remote folder.");
        if (!Directory.Exists(localFolder)) throw new ArgumentException("Select an existing local folder.");
        if ((File.GetAttributes(localFolder) & FileAttributes.ReparsePoint) != 0) throw new ArgumentException("Select a regular folder, not a symbolic link or junction.");
        using var commit = await SendAsync(repository, "commits/" + Uri.EscapeDataString(branch), token, null, ct);
        var sha = commit.RootElement.GetProperty("sha").GetString()!;
        var treeSha = commit.RootElement.GetProperty("commit").GetProperty("tree").GetProperty("sha").GetString()!;
        using var tree = await SendAsync(repository, "git/trees/" + treeSha + "?recursive=1", token, null, ct);
        if (!tree.RootElement.TryGetProperty("truncated", out var truncated) || truncated.GetBoolean()) throw new InvalidOperationException("GitHub returned an incomplete tree. Comparison was stopped; no missing-file conclusions were made.");
        var prefix = remoteFolder.Length == 0 ? "" : remoteFolder + "/";
        var remote = new Dictionary<string, (string Sha, bool Regular)>(StringComparer.Ordinal);
        foreach (var item in tree.RootElement.GetProperty("tree").EnumerateArray())
        {
            var path = item.GetProperty("path").GetString()!;
            if (!path.StartsWith(prefix, StringComparison.Ordinal)) continue;
            var type = item.GetProperty("type").GetString();
            if (type == "tree") continue;
            var mode = item.GetProperty("mode").GetString();
            remote.Add(path[prefix.Length..], (item.GetProperty("sha").GetString()!, type == "blob" && mode is "100644" or "100755"));
        }
        var rows = new List<ComparisonRow>();
        await Task.Run(async () =>
        {
            var pending = new Stack<string>(); pending.Push(localFolder);
            var seen = new HashSet<string>(StringComparer.Ordinal);
            while (pending.Count > 0)
            {
                ct.ThrowIfCancellationRequested();
                foreach (var entry in Directory.EnumerateFileSystemEntries(pending.Pop()))
                {
                    ct.ThrowIfCancellationRequested();
                    if (string.Equals(System.IO.Path.GetFileName(entry), ".git", StringComparison.OrdinalIgnoreCase)) continue;
                    var relative = System.IO.Path.GetRelativePath(localFolder, entry).Replace('\\', '/');
                    var attributes = File.GetAttributes(entry);
                    if ((attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidOperationException("Comparison stopped at a symbolic link or junction: " + relative);
                    if ((attributes & FileAttributes.Directory) != 0) { pending.Push(entry); continue; }
                    if (seen.Count >= 50000) throw new InvalidOperationException("Comparison supports at most 50,000 local files. Select a smaller folder.");
                    seen.Add(relative);
                    if (!remote.TryGetValue(relative, out var target)) { rows.Add(new(relative, "Local only")); continue; }
                    if (!target.Regular) { rows.Add(new(relative, "Unsupported remote link/submodule")); continue; }
                    var hash = await HashBlobAsync(entry, ct);
                    rows.Add(new(relative, string.Equals(hash, target.Sha, StringComparison.OrdinalIgnoreCase) ? "Same content" : "Changed content"));
                }
            }
            foreach (var target in remote.Where(x => !seen.Contains(x.Key))) rows.Add(new(target.Key, target.Value.Regular ? "Remote only" : "Unsupported remote link/submodule"));
        }, ct);
        return new(sha, rows.OrderBy(x => x.Path, StringComparer.Ordinal).ToArray());
    }

    public async Task<string> CreateBranchAsync(string repository, string sourceBranch, string newBranch, string token, CancellationToken ct = default)
    {
        ValidateRepository(repository); ValidateBranch(sourceBranch); ValidateBranch(newBranch);
        using var source = await SendAsync(repository, "git/ref/heads/" + EncodePath(sourceBranch), token, null, ct);
        var sha = source.RootElement.GetProperty("object").GetProperty("sha").GetString()!;
        using var created = await SendAsync(repository, "git/refs", token, new { @ref = "refs/heads/" + newBranch, sha }, ct);
        return created.RootElement.GetProperty("ref").GetString()!;
    }

    public async Task<string> CreatePullRequestAsync(string repository, string head, string baseBranch, string title, string body, bool draft, string token, CancellationToken ct = default)
    {
        ValidateRepository(repository); ValidateBranch(head); ValidateBranch(baseBranch);
        if (head == baseBranch) throw new ArgumentException("Head and base branches must differ.");
        if (string.IsNullOrWhiteSpace(title)) throw new ArgumentException("Enter a pull-request title.");
        using var created = await SendAsync(repository, "pulls", token, new { head, @base = baseBranch, title = title.Trim(), body, draft }, ct);
        return created.RootElement.GetProperty("html_url").GetString()!;
    }

    public static async Task<string> HashBlobAsync(string path, CancellationToken ct = default)
    {
        using var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 81920, true);
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA1);
        hash.AppendData(Encoding.ASCII.GetBytes("blob " + file.Length.ToString(System.Globalization.CultureInfo.InvariantCulture) + "\0"));
        var buffer = new byte[81920]; int read;
        while ((read = await file.ReadAsync(buffer.AsMemory(), ct)) > 0) hash.AppendData(buffer, 0, read);
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private async Task<JsonDocument> SendAsync(string repository, string route, string token, object? payload, CancellationToken ct)
    {
        if (string.IsNullOrWhiteSpace(token) || token.Any(char.IsControl)) throw new ArgumentException("Sign in to GitHub first.");
        using var request = new HttpRequestMessage(payload == null ? HttpMethod.Get : HttpMethod.Post, "https://api.github.com/repos/" + EncodePath(repository) + "/" + route);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.5");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        if (payload != null) request.Content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
        using var response = await _http.SendAsync(request, ct);
        if (!response.IsSuccessStatusCode) throw new HttpRequestException($"GitHub returned HTTP {(int)response.StatusCode}. Check access, branch names, quota, and whether the branch or pull request already exists. Pull requests need differing commits.", null, response.StatusCode);
        return await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync(ct), cancellationToken: ct);
    }
    private static string EncodePath(string value) => string.Join("/", value.Split('/').Select(Uri.EscapeDataString));
    public static void ValidateRepository(string repository)
    {
        if (!Regex.IsMatch(repository, "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$") || repository.Split('/').Any(x => x is "." or "..")) throw new ArgumentException("Enter a repository as owner/name.");
    }
    public static void ValidateBranch(string branch)
    {
        if (string.IsNullOrWhiteSpace(branch) || branch.Length > 255 || branch == "@" || branch.StartsWith('-') || branch.EndsWith('.') || branch.Contains("..") || branch.Contains("@{") || branch.Any(c => char.IsControl(c) || c is ' ' or '~' or '^' or ':' or '?' or '*' or '[' or '\\') || branch.Split('/').Any(x => x.Length == 0 || x.StartsWith('.') || x.EndsWith(".lock", StringComparison.OrdinalIgnoreCase))) throw new ArgumentException("Enter a valid Git branch name.");
    }
}
