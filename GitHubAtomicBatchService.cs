using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace FileToGitHub;

/// <summary>Publishes a complete batch by creating Git objects then advancing the branch once.</summary>
public sealed class GitHubAtomicBatchService
{
    private readonly HttpClient _http;
    public GitHubAtomicBatchService(HttpClient http) => _http = http ?? throw new ArgumentNullException(nameof(http));

    public async Task<string> GetHeadAsync(string owner, string repository, string branch, string token, CancellationToken ct = default)
    {
        Validate(owner, repository, branch, token);
        using var head = await SendAsync(HttpMethod.Get, Root(owner, repository) + "/git/ref/heads/" + EncodePath(branch), token, null, ct);
        return head.RootElement.GetProperty("object").GetProperty("sha").GetString()!;
    }

    public async Task<IReadOnlyList<BatchUploadResult>> UploadAsync(string owner, string repository, string branch,
        string token, IReadOnlyList<BatchUploadFile> files, string message, string expectedHeadSha,
        IProgress<BatchUploadProgress>? progress = null, CancellationToken ct = default,
        Func<string, byte[], CancellationToken, Task>? validateContent = null)
    {
        Validate(owner, repository, branch, token);
        if (files.Count is < 1 or > 100) throw new ArgumentException("A batch must contain between 1 and 100 files.");
        if (string.IsNullOrWhiteSpace(message) || message.Length > 250) throw new ArgumentException("Enter a commit message of 1 to 250 characters.");
        if (expectedHeadSha == null || !Regex.IsMatch(expectedHeadSha, "^[0-9a-fA-F]{40}$")) throw new ArgumentException("A reviewed branch commit SHA is required.");
        var paths = new HashSet<string>(StringComparer.Ordinal);
        foreach (var file in files)
        {
            var path = UploadQueueItem.NormalizeDestination(file.DestinationPath);
            if (path != file.DestinationPath || path.Any(char.IsControl) || !paths.Add(path))
                throw new ArgumentException("Each destination must be a unique, safe repository path.");
            if (file.Size is < 0 or > 50 * 1024 * 1024) throw new InvalidOperationException("Each file must be at most 50 MiB.");
        }
        if (paths.Any(path => paths.Any(other => path.StartsWith(other + "/", StringComparison.Ordinal))))
            throw new InvalidOperationException("A file destination cannot also be another file's parent folder.");
        var root = Root(owner, repository);
        using (var repo = await SendAsync(HttpMethod.Get, root, token, null, ct))
        {
            var r = repo.RootElement;
            if (r.GetProperty("archived").GetBoolean() || r.GetProperty("disabled").GetBoolean() ||
                !r.TryGetProperty("permissions", out var permissions) || !permissions.TryGetProperty("push", out var push) || push.ValueKind != JsonValueKind.True)
                throw new InvalidOperationException("GitHub must confirm write permission on an active repository.");
        }
        await RequireHeadAsync(owner, repository, branch, token, expectedHeadSha, ct);
        using var parent = await SendAsync(HttpMethod.Get, root + "/git/commits/" + expectedHeadSha, token, null, ct);
        var baseTree = parent.RootElement.GetProperty("tree").GetProperty("sha").GetString();
        using var existingTree = await SendAsync(HttpMethod.Get, root + "/git/trees/" + baseTree + "?recursive=1", token, null, ct);
        if (existingTree.RootElement.TryGetProperty("truncated", out var truncated) && truncated.GetBoolean())
            throw new InvalidOperationException("GitHub truncated the repository tree. This batch cannot safely check file modes and destinations.");
        var existingEntries = existingTree.RootElement.GetProperty("tree").EnumerateArray()
            .ToDictionary(x => x.GetProperty("path").GetString()!, x => x.GetProperty("mode").GetString()!, StringComparer.Ordinal);
        foreach (var file in files)
        {
            if (existingEntries.TryGetValue(file.DestinationPath, out var mode) && mode is not ("100644" or "100755"))
                throw new InvalidOperationException("The destination is a directory, symbolic link or submodule. Choose a new file path.");
            var parentPath = file.DestinationPath;
            while (parentPath.LastIndexOf('/') is var separator && separator >= 0)
            {
                parentPath = parentPath.Substring(0, separator);
                if (existingEntries.TryGetValue(parentPath, out var parentMode) && parentMode != "040000")
                    throw new InvalidOperationException("A destination parent is a file, symbolic link or submodule. Choose a new path.");
            }
        }
        var reviewedHashes = new Dictionary<string, byte[]>(StringComparer.Ordinal);
        // Inspect the exact content of every file before creating any remote object.
        foreach (var file in files)
        {
            var bytes = await ReadStableAsync(file, ct);
            if (validateContent != null) await validateContent(file.SourcePath, bytes, ct);
            reviewedHashes[file.DestinationPath] = SHA256.HashData(bytes);
        }
        var treeEntries = new List<object>();
        foreach (var file in files)
        {
            ct.ThrowIfCancellationRequested();
            var bytes = await ReadStableAsync(file, ct);
            if (!SHA256.HashData(bytes).SequenceEqual(reviewedHashes[file.DestinationPath]))
                throw new InvalidOperationException("A file changed after content review. Nothing was published by this attempt.");
            using var blob = await SendAsync(HttpMethod.Post, root + "/git/blobs", token,
                new { content = Convert.ToBase64String(bytes), encoding = "base64" }, ct);
            treeEntries.Add(new { path = file.DestinationPath, mode = existingEntries.GetValueOrDefault(file.DestinationPath, "100644"), type = "blob", sha = blob.RootElement.GetProperty("sha").GetString() });
            progress?.Report(new BatchUploadProgress(file.SourcePath, 85));
        }
        using var tree = await SendAsync(HttpMethod.Post, root + "/git/trees", token, new { base_tree = baseTree, tree = treeEntries }, ct);
        using var commit = await SendAsync(HttpMethod.Post, root + "/git/commits", token,
            new { message, tree = tree.RootElement.GetProperty("sha").GetString(), parents = new[] { expectedHeadSha } }, ct);
        var commitSha = commit.RootElement.GetProperty("sha").GetString()!;
        await RequireHeadAsync(owner, repository, branch, token, expectedHeadSha, ct);
        // Never force: if the branch advances during publication GitHub rejects the non-fast-forward update.
        try
        {
            using var updated = await SendAsync(HttpMethod.Patch, root + "/git/refs/heads/" + EncodePath(branch), token,
                new { sha = commitSha, force = false }, ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or OperationCanceledException)
        {
            throw new InvalidOperationException($"Publication was not confirmed. Check GitHub commit {commitSha} before retrying; the branch update may have completed.", ex);
        }
        foreach (var file in files) progress?.Report(new BatchUploadProgress(file.SourcePath, 100));
        return files.Select(file => new BatchUploadResult(file.SourcePath, true,
            $"https://github.com/{Uri.EscapeDataString(owner)}/{Uri.EscapeDataString(repository)}/blob/{commitSha}/{EncodePath(file.DestinationPath)}")).ToArray();
    }

    private static async Task<byte[]> ReadStableAsync(BatchUploadFile file, CancellationToken ct)
    {
        await using var stream = new FileStream(file.SourcePath, FileMode.Open, FileAccess.Read, FileShare.Read, 131072, true);
        if (stream.Length != file.Size || (file.CapturedLastWriteTimeUtc.HasValue && File.GetLastWriteTimeUtc(file.SourcePath) != file.CapturedLastWriteTimeUtc.Value))
            throw new InvalidOperationException("A local file changed after review. Rebuild and review the queue.");
        using var buffer = new MemoryStream(checked((int)file.Size));
        await stream.CopyToAsync(buffer, ct);
        return buffer.ToArray();
    }

    private async Task RequireHeadAsync(string owner, string repo, string branch, string token, string expected, CancellationToken ct)
    {
        if (!string.Equals(await GetHeadAsync(owner, repo, branch, token, ct), expected, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("The GitHub branch changed after review. Reopen the batch to review remote conflicts again. Nothing was published by this attempt.");
    }
    private async Task<JsonDocument> SendAsync(HttpMethod method, string path, string token, object? body, CancellationToken ct)
    {
        using var request = new HttpRequestMessage(method, "https://api.github.com" + path);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        request.Headers.UserAgent.ParseAdd("OctoShip-for-GitHub/1.5");
        request.Headers.Accept.ParseAdd("application/vnd.github+json");
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        if (body != null) request.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        using var response = await _http.SendAsync(request, ct);
        if (!response.IsSuccessStatusCode) throw new HttpRequestException($"GitHub returned HTTP {(int)response.StatusCode}. Check repository access, branch protection, conflicts, and API limits.", null, response.StatusCode);
        return JsonDocument.Parse(await response.Content.ReadAsStringAsync(ct));
    }
    private static string Root(string owner, string repo) => $"/repos/{Uri.EscapeDataString(owner)}/{Uri.EscapeDataString(repo)}";
    private static string EncodePath(string value) => string.Join("/", value.Split('/').Select(Uri.EscapeDataString));
    private static void Validate(string owner, string repo, string branch, string token)
    {
        if (new[] { owner, repo }.Any(x => string.IsNullOrWhiteSpace(x) || x is "." or ".." || !Regex.IsMatch(x, "^[A-Za-z0-9_.-]+$"))) throw new ArgumentException("Invalid repository identity.");
        if (string.IsNullOrWhiteSpace(token) || token.Any(char.IsControl)) throw new ArgumentException("A connected account credential is required.");
        if (string.IsNullOrWhiteSpace(branch) || branch.StartsWith('/') || branch.EndsWith('/') || branch.Contains("..") || branch.Contains("//") || branch.Contains("@{") || branch.Any(c => char.IsControl(c) || " ~^:?*[\\".Contains(c))) throw new ArgumentException("Invalid branch name.");
    }
}
